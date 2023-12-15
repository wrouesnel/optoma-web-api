from optoma_web_api import Projector

EXT = "http://192.168.1.63"

from pprint import pprint


def test_status():
    p = Projector(EXT)
    status = p.status()
    pprint(status)


def test_power_off():
    p = Projector(EXT)
    p.power_off()


def test_power_on():
    p = Projector(EXT)
    p.power_off()
