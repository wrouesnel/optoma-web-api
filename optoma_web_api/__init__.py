import hashlib
import inspect
import logging
import typing
from typing import Dict

import pyparsing as pp
import pyparsing.exceptions
import requests
import retrying
from bs4 import BeautifulSoup
from furl import furl

logger = logging.getLogger()

status_grammer = (
    pp.Char("{").suppress()
    + pp.OneOrMore(
        pp.Group(pp.Word(pp.alphas) + pp.Char(":").suppress() + pp.QuotedString('"'))
        + pp.Optional(",").suppress()
    )
    + pp.Char("}").suppress()
)


class ProjectorException(Exception):
    pass


class LoginPageFailure(ProjectorException):
    def __init__(self):
        super().__init__("Failed to find the login challenge on the login page")


class LoginFailure(ProjectorException):
    pass

class NotLoggedIn(ProjectorException):
    """Returned when not logged in"""
    pass

def _parse_status_response(status_response: str) -> Dict[str, str]:
    try:
        parsed_response = status_grammer.parse_string(status_response)
        return {k: v for k, v in parsed_response}
    except pyparsing.exceptions.ParseException as e:
        logger.error(
            "Error parsing response: %s %s", str(e), status_response, exc_info=e
        )
        raise e

# This value is returned when a value is stubbed out
VALUE_NOT_AVAILABLE = "N/A"

# This is the map of status returns to human-usable values. Format is a dictionary of
# literal values, or a function to a value which can do the translation where applicable.
STATUS_VALUE_MAP = {
    "Power Status": {
        "0": "Off",
        "1": "On",
    },
    "Source": {
        "0": "HDMI 1",
        "1": "HDMI 2/MHL",
        "2": "VGA",
    },
    "Display Mode": {
        "0": "Presentation",
        "1": "Bright",
        "2": "Unknown 3D Mode 1", # Unknown 3D Mode?
        "3": "Unknown 3D Mode 2", # Unknown 3D Mode?
        "4": "HDR SIM.",
        "5": "Cinema",
        "6": "Game",
        "7": "sRGB",
        "8": "DICOM SIM",
        "9": "HDR2",
        "255": VALUE_NOT_AVAILABLE,
    },
    "Brightness": int,
    "Contrast": int,
    "Sharpness": int,
    "Projection": {
        "0": "Front",
        "1": "Ceiling-top",
        "2": "Rear",
        "3": "Rear-top",
    },
    "Brightness Mode": {
        "0": VALUE_NOT_AVAILABLE,
        "4": "DynamicBlack 1",
        "5": "DynamicBlack 2",
        "6": "DynamicBlack 3",
        "7": "Power 100%",
        "8": "Power 95%",
        "9": "Power 90%",
        "10": "Power 85%",
        "11": "Power 80%",
        "12": "Power 75%",
        "13": "Power 70%",
        "14": "Power 65%",
        "15": "Power 60%",
        "16": "Power 55%",
        "17": "Power 50%",
    },
    "AV Mute": {
        "0": "Off",
        "1": "On",
    },
    "Power Mode": {
        "0": "Active",
        "1": "Eco.",
    },
    "Freeze": {
        "0": "Off",
        "1": "On",
    },
    "Logo": {
        "0": "Default",
        "2": "Neutral",
    },
    "Color Space": {
        "0": "Auto",
        "1": "RGB",
        "2": "RGB(0-255)",
        "3": "RGB(16-235)",
        "4": "YUV",
    },
    "Zoom": int,
    "Auto Power Off": int,
    "Background Color": {
        "0": "None",
        "1": "Blue",
        "2": "Red",
        "3": "Green",
        "4": "Gray",
    },
    "Wall Color": {
        "0": "Off",
        "1": "BlackBoard",
        "2": "Light Yellow",
        "3": "Light Green",
        "4": "Light Blue",
        "5": "Pink",
        "6": "Gray",
    },
    "Always On": {
        "0": "Off",
        "1": "On",
    },
    "Phase": int,
    "BrilliantColor": int,
    "Gamma": {
        "0": "Film",
        "1": "Video",
        "2": "Graphics",
        "3": "Standard(2.2)",
        "4": "1.8",
        "5": "2.0",
        "6": "2.4",
        "7": "3D",
        "8": "2.6",
        "9": "HDR",
        "10": "HLG",
        "11": "Blackboard",
        "12": "DICOM SIM",
        "255": VALUE_NOT_AVAILABLE,
    },
    "Color Temperature": {
        "0": "Warm",
        "1": "Standard",
        "2": "Cool",
        "3": "Cold",
    },
    "Sleep": int,
    "Aspect Ratio": {
        "0": "4:3",
        "1": "16:9",
        "3": "LBX",
        "4": "Native",
        "5": "Auto",
        "6": "SuperWide",
        "255": VALUE_NOT_AVAILABLE,
    },
    "Horizontal Image Shift": int,
    "Vertical Image Shift": int,
    "High Altitude": {
        "0": "Off",
        "1": "On",
    },
    "Direct Power On": {
        "0": "Off",
        "1": "On",
    },
    "Projector ID": int,
    #"Screen Type": {}
    "Information Hide": {
        "0": "Off",
        "1": "On",
    },
    "Display Mode Lock": {
        "0": "Off",
        "1": "On",
    },
    "Keypad Lock": {
        "0": "Off",
        "1": "On",
    },
}

# Back-mapping of values to codes
STATUS_VALUE_TO_CODE_MAP = { k: { sv:sk for sk,sv in STATUS_VALUE_MAP[k].items() } for k in [ k for k in STATUS_VALUE_MAP if isinstance(STATUS_VALUE_MAP[k], typing.Mapping) ] }

# Map of names to buttons which have no status representation
BUTTONS = {
    "Resync": "resync",
    "Reset": "reset",
}

STATUS_TO_NAME_MAP = {
    "pw": "Power Status",
    "a": "Source",
    "b": "Display Mode",
    "c": "Brightness",
    "d": "Contrast",
    "f": "Sharpness",
    "t": "Projection",
    "h": "Brightness Mode",
    "j": None, # Apparently not handled?
    "k": "AV Mute",
    "l": "Power Mode",
    "m": None, # Apparently not handled?
    "n": "Freeze",
    "o": "Logo",
    "p": None,
    "q": "Color Space",
    "r": "Zoom",
    "u": "Auto Power Off",
    "v": None, # Apparently not handled
    "w": None, # Degamma related - disables option 8 if 1
    "x": "Background Color",
    "y": "Wall Color",
    "z": "Always On",
    "A": "Phase",
    "B": "BrilliantColor",
    "C": "Gamma",
    "D": "Color Temperature",
    "E": None, # undefined
    "H": "Sleep",
    "I": None, # Undefined
    "K": None, # Undefined
    "L": "Aspect Ratio",
    "M": "Horizontal Image Shift",
    "N": "Vertical Image Shift",
    "O": "High Altitude",
    "P": "Direct Power On",
    "Q": "Projector ID",
    "R": None,  # aspect ratio parameter of some sort
    "S": None,  # screen type type parameter of some sort
    "T": None, # undefined
    "V": "Information Hide",
    "W": "Display Mode Lock",
    "Y": "Keypad Lock",
    "e": None,  ## Phase Mode?
    "g": None,  ## Display mode?
    "Z": None,  ## Src select display?
}

class Projector:
    def __init__(
        self,
        url: str,
        username: str = "admin",
        password: str = "admin",
        retry_limit_count=3,
        retry_interval_secs=1,
    ):
        """
        Initialize a new projector object.

        Note: For the projector I have access to, the password is *always* admin.

        :param url: HTTP URL to the projector
        """
        self._base_url = furl(url)
        self._username = username
        self._password = password
        self._session = requests.Session()

        self._logged_in = False

        self._retry_limit_count = retry_limit_count
        self._retry_interval_secs = retry_interval_secs
        self._retry_decorator = retrying.retry(
            wait_fixed=self._retry_interval_secs * 1000,
            stop_max_attempt_number=self._retry_limit_count,
        )

    @property
    def url(self):
        return str(self._base_url)

    def _check_response_for_login_scheme(self, resp) -> BeautifulSoup:
        # The projector has a tendency to dump us back into "please login" randomly,
        # so check if the result looks like HTML here.
        parsed_response = BeautifulSoup(resp.text, features="html.parser")
        login_frame = parsed_response.find("frame", {"src": "/login.htm"})
        if login_frame:
            raise NotLoggedIn()
        return parsed_response

    def _info(self) -> Dict[str,str]:
        """Handle retrieving basic info from the projector"""
        resp = self._session.get(self._base_url / "Info.htm")
        resp.raise_for_status()
        parsed_response = self._check_response_for_login_scheme(resp)
        # Seem to have received a real response, let's parse it.

        info_div = parsed_response.select_one("div", {"classname": "tbi"})
        info_rows = info_div.select("tr")

        result: Dict[str,str] = {}

        for tr in info_rows:
            ths = tr.select("th")
            if len(ths) > 0:
                kvs = [ th.text for th in ths ]
                if len(kvs) == 2:
                    key, value = kvs[0], kvs[1]
                else:
                    continue
            else:
                tds = tr.select("td")
                kvs = [td.text for td in tds]
                if len(kvs) == 2:
                    key, value = kvs[0], kvs[1]
                else:
                    continue
            result[key] = value
        return result

    def info(self) -> Dict[str,str]:
        decorator = retrying.retry(
            retry_on_exception=self._control_retry,
            wait_fixed=self._retry_interval_secs * 1000,
            stop_max_attempt_number=self._retry_limit_count,
        )
        resp = decorator(self._info)()
        return resp

    def _control(self, data=None):
        """Handle making an authenticated request to the projector"""
        resp = self._session.post(self._base_url / "tgi" / "control.tgi", data=data)
        resp.raise_for_status()
        self._check_response_for_login_scheme(resp)
        return resp

    def _control_retry(self, exception):
        """Manage retry logic"""
        if isinstance(exception, NotLoggedIn):
            logger.debug("Command failed due to not logged in error - executing login")
            self._logged_in = False
            self._login()
            logger.debug("Login successful, retrying")
            return True
        elif isinstance(exception, requests.exceptions.ConnectionError):
            # Always retry a connection error
            return True
        return False

    def control(self, data=None):
        """Send a request to the projector web interface"""
        # if not self._logged_in:
        #     self._login()
        decorator = retrying.retry(
            retry_on_exception=self._control_retry,
            wait_fixed=self._retry_interval_secs * 1000,
            stop_max_attempt_number=self._retry_limit_count,
        )
        resp = decorator(self._control)(data=data)
        return resp

    def _login(self):
        try:
            login_page = self._session.get(self._base_url / "login.htm")
            login_page_tags = BeautifulSoup(login_page.content, features="html.parser")
            challenge = login_page_tags.find("input", {"name": "Challenge"})["value"]
        except Exception as e:
            raise LoginPageFailure() from e

        login_request = {
            "user": "0",
            "Username": "1",
            "Password": "",
            "Challenge": "",
            "Response": hashlib.md5(
                f"{self._username}{self._password}{challenge}".encode("utf8")
            ).hexdigest(),
        }

        try:
            resp = self._session.post(
                self._base_url / "tgi" / "login.tgi", data=login_request
            )
            resp.raise_for_status()
        except Exception as e:
            raise LoginFailure("HTTP error while sending login response") from e

        # Check the response contains a cookie to set
        if "ATOP" not in resp.cookies:
            raise LoginFailure("No authorization cookie in admin response")

        self._logged_in = True

    def _status_request(self) -> str:
        resp = self.control({"QueryControl": ""})
        return resp.text.replace("\n", "")

    def status(self) -> Dict[str, str]:
        """Get the current status of the projector"""
        status_text = self._status_request()
        result = _parse_status_response(status_text)

        status = {
            STATUS_TO_NAME_MAP[k]: v
            for k, v in result.items() if STATUS_TO_NAME_MAP[k] is not None
        }

        result_status = {}

        # Parse the values
        for name, value in status.items():
            if name not in STATUS_VALUE_MAP:
                logging.warning("No mapping for parameter: %s", name)

            value_mapping = STATUS_VALUE_MAP.get(name)
            if isinstance(value_mapping, typing.Mapping):
                if value not in value_mapping:
                    logger.warning("No mapping for %s: %s", name, value)
                result_status[name] = value_mapping.get(value, value)
            elif isinstance(value_mapping, typing.Callable):
                if inspect.isclass(value_mapping):
                    # Classes are type conversions, just handle the value
                    fn_param_count = 1
                else:
                    fn_sig = inspect.signature(value_mapping)
                    fn_param_count = len(fn_sig.parameters)
                # Callable - does it accept 2 parameters?
                if fn_param_count == 1:
                    result_status[name] = value_mapping(value)
                elif fn_param_count == 2:
                    result_status[name] = value_mapping(value, status)
                else:
                    raise NotImplementedError("Callable with an invalid number of parameters!")
            else:
                raise NotImplementedError("Unhandled type - not mapping or function!")

        return result_status

    def power_off(self):
        try:
            self.control(
                {
                    "btn_powoff": "Power Off"
                    # "btn_powon": "Power Off"
                }
            )
        except Exception as e:
            logger.warning(f"Error sending power off command: {str(e)}")
            raise e

    def power_on(self):
        try:
            self.control({"btn_powon": "Power On"})
        except Exception as e:
            logger.warning(f"Error sending power on command: {str(e)}")
            raise e

    def power_status(self, value: typing.Union[int,str]):
        """Power Status is a specialized control command because it doesn't quite map to the interface"""
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        if set_value == "1":
            return self.power_on()
        else:
            return self.power_off()

    def resync(self):
        try:
            self.control({"resync": "Resync"})
        except Exception as e:
            logger.warning(f"Error sending resync command: {str(e)}")
            raise e

    def reset(self):
        try:
            self.control({"reset": "Reset"})
        except Exception as e:
            logger.warning(f"Error sending reset command: {str(e)}")
            raise e

    def avmute(self):
        try:
            self.control({"avmute": "AV Mute"})
        except Exception as e:
            logger.warning(f"Error sending avmute command: {str(e)}")
            raise e

    def freeze(self):
        try:
            self.control({"freeze": "AV Mute"})
        except Exception as e:
            logger.warning(f"Error sending freeze command: {str(e)}")
            raise e

    def infohide(self):
        try:
            self.control({"infohide": "Information Hide"})
        except Exception as e:
            logger.warning(f"Error sending infohide command: {str(e)}")
            raise e

    def altitude(self):
        try:
            self.control({"altitude": "High Altitude"})
        except Exception as e:
            logger.warning(f"Error sending altitude command: {str(e)}")
            raise e

    def keypad(self):
        try:
            self.control({"keypad": "Keypad Lock"})
        except Exception as e:
            logger.warning(f"Error sending keypad command: {str(e)}")
            raise e

    def dismdlocked(self):
        try:
            self.control({"dismdlocked": "Display Mode Lock"})
        except Exception as e:
            logger.warning(f"Error sending dismdlocked command: {str(e)}")
            raise e

    def directpwon(self):
        try:
            self.control({"directpwon": "Direct Power On"})
        except Exception as e:
            logger.warning(f"Error sending directpwon command: {str(e)}")
            raise e

    def alwayson(self):
        try:
            self.control({"alwayson": "Always On"})
        except Exception as e:
            logger.warning(f"Error sending alwayson command: {str(e)}")
            raise e

    def source(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"source": set_value})
        except Exception as e:
            logger.warning(f"Error sending source command: {str(e)}")
            raise e

    def brightness(self, value: int):
        set_value = str(value)
        try:
            self.control({"bright": set_value})
        except Exception as e:
            logger.warning(f"Error sending brightness command: {str(e)}")
            raise e

    def contrast(self, value: int):
        set_value = str(value)
        try:
            self.control({"contrast": set_value})
        except Exception as e:
            logger.warning(f"Error sending contrast command: {str(e)}")
            raise e

    def sharpness(self, value: int):
        # Note: apparently cannot be set below 1?
        set_value = str(value)
        try:
            self.control({"Sharp": set_value})
        except Exception as e:
            logger.warning(f"Error sending sharpness command: {str(e)}")
            raise e

    def phase(self, value: int):
        # Note: not sure when you can set this?
        set_value = str(value)
        try:
            self.control({"Phase": set_value})
        except Exception as e:
            logger.warning(f"Error sending phase command: {str(e)}")
            raise e

    def brilliantcolor(self, value: int):
        # Note: apparently can't actually be set below 1?
        set_value = str(value)
        try:
            self.control({"brill": set_value})
        except Exception as e:
            logger.warning(f"Error sending brilliantcolor command: {str(e)}")
            raise e

    def gamma(self, value: typing.Union[int,str]):
        # Note: AFAIK 255 means "N/A"
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"Degamma": set_value})
        except Exception as e:
            logger.warning(f"Error sending gamma command: {str(e)}")
            raise e

    def color_temperature(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"colortmp": set_value})
        except Exception as e:
            logger.warning(f"Error sending color_temperature command: {str(e)}")
            raise e

    def display_mode(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"dismode": set_value})
        except Exception as e:
            logger.warning(f"Error sending display_mode command: {str(e)}")
            raise e

    def color_space(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"colorsp": set_value})
        except Exception as e:
            logger.warning(f"Error sending color_space command: {str(e)}")
            raise e

    def aspect_ratio(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"aspect1": set_value})
        except Exception as e:
            logger.warning(f"Error sending aspect_ratio command: {str(e)}")
            raise e

    def projection(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"projection": set_value})
        except Exception as e:
            logger.warning(f"Error sending projection command: {str(e)}")
            raise e

    def zoom(self, value: int):
        set_value = str(value)
        try:
            self.control({"zoom": set_value})
        except Exception as e:
            logger.warning(f"Error sending zoom command: {str(e)}")
            raise e

    def horizontal_image_shift(self, value: int):
        set_value = str(value)
        try:
            self.control({"hpos": set_value})
        except Exception as e:
            logger.warning(f"Error sending horizontal_image_shift command: {str(e)}")
            raise e

    def vertical_image_shift(self, value: int):
        set_value = str(value)
        try:
            self.control({"vpos": set_value})
        except Exception as e:
            logger.warning(f"Error sending vertical_image_shift command: {str(e)}")
            raise e

    def auto_power_off(self, value: int):
        set_value = str(value)
        try:
            self.control({"autopw": set_value})
        except Exception as e:
            logger.warning(f"Error sending auto_power_off command: {str(e)}")
            raise e

    def sleep_timer(self, value: int):
        set_value = str(value)
        try:
            self.control({"sleep": set_value})
        except Exception as e:
            logger.warning(f"Error sending sleep_timer command: {str(e)}")
            raise e

    def projector_id(self, value: int):
        set_value = str(value)
        try:
            self.control({"projid": set_value})
        except Exception as e:
            logger.warning(f"Error sending projector_id command: {str(e)}")
            raise e

    def background_color(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"background": set_value})
        except Exception as e:
            logger.warning(f"Error sending background_color command: {str(e)}")
            raise e

    def wall_color(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"wall": set_value})
        except Exception as e:
            logger.warning(f"Error sending wall_color command: {str(e)}")
            raise e

    def logo(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"logo": set_value})
        except Exception as e:
            logger.warning(f"Error sending logo command: {str(e)}")
            raise e

    def power_mode(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"pwmode": set_value})
        except Exception as e:
            logger.warning(f"Error sending power_mode command: {str(e)}")
            raise e

    def brightness_mode(self, value: typing.Union[int,str]):
        set_value = str(value) if isinstance(value, int) else STATUS_VALUE_TO_CODE_MAP[value]
        try:
            self.control({"lampmd": set_value})
        except Exception as e:
            logger.warning(f"Error sending brightness_mode command: {str(e)}")
            raise e

    def mac_address(self) -> str:
        """Get the MAC address of the projector"""
        try:
            info_response = self._info()
        except Exception as e:
            logger.warning(f"Error getting projector info: {str(e)}")
            raise e

        return info_response["MAC Address"]
