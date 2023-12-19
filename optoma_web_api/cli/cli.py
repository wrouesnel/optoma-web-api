import datetime
import logging
import sys
import time
from typing import Any, Callable

import click
import inflection
import pyrfc3339
from click.decorators import pass_meta_key
from tzlocal import get_localzone

from optoma_web_api import Projector, STATUS_VALUE_MAP, STATUS_VALUE_TO_CODE_MAP
from optoma_web_api.cli import clitypes

logger = logging.getLogger()

OUTPUT_FN = f"{__name__}.output_format_function"

pass_projector = click.make_pass_decorator(Projector)
pass_output_func = pass_meta_key(
    OUTPUT_FN, doc_description="Output function for structured data"
)


@click.group(context_settings={"auto_envvar_prefix": "OPTOMA"})
@click.option(
    "--output-format",
    "-o",
    type=clitypes.OutputFormat(),
    default="json",
    help="Output format",
)
@click.option("--url", help="HTTP URL for the Projector Interface")
@click.option(
    "--username", default="admin", help="Username for logging into the projector"
)
@click.option(
    "--password", default="admin", help="Password for logging into the projector"
)
@click.pass_context
def cli(ctx, output_format: clitypes.OutputFn, url: str, username: str, password: str):
    """Optoma Command Line Interface"""
    logging.basicConfig(stream=sys.stderr)

    projector = Projector(url, username=username, password=password)
    ctx.obj = projector
    ctx.meta[OUTPUT_FN] = output_format


@cli.command("status")
@click.option(
    "--monitor",
    "-m",
    type=click.BOOL,
    is_flag=True,
    default=False,
    help="Continuously monitor the status",
)
@click.option(
    "--difference",
    "-d",
    type=click.BOOL,
    is_flag=True,
    default=False,
    help="Print only values which change - no effect without --monitor",
)
@pass_projector
@pass_output_func
def status(output_func: clitypes.OutputFn, projector: Projector, monitor: bool, difference: bool):
    """Get current projector status"""
    previous_status = {}

    if difference:
        logger.info("Emitting changes to state only")

    while True:
        status_result = projector.status()
        emitted_result = status_result

        if difference:
            emitted_result = { k:v for k,v in status_result.items() if k not in previous_status or previous_status.get(k) != status_result.get(k) }

        previous_status = status_result

        if len(emitted_result) != 0:
            click.echo(
                pyrfc3339.generate(datetime.datetime.now(tz=get_localzone())), err=True
            )  # Include a timestamp
            click.echo(output_func(emitted_result))

        if not monitor:
            break
        time.sleep(1)

@cli.command("info")
@pass_projector
@pass_output_func
def cli_info(output_func: clitypes.OutputFn, projector: Projector):
    """Get the Unique ID of the projector"""
    click.echo(output_func(projector.info()))

@cli.command("unique-id")
@pass_projector
@pass_output_func
def cli_uniqueid(output_func: clitypes.OutputFn, projector: Projector):
    """Get the Unique ID of the projector"""
    click.echo(output_func(projector.info()["MAC Address"]))

@cli.group("control")
def cli_control():
    """Issue a control command to the projector"""

def _make_control_command(name: str) -> click.Command:
    """Make a control command for the projector"""
    friendly_name = name
    command_name = inflection.parameterize(name)
    fn_name = inflection.underscore(name)

    @click.command(command_name)
    @click.argument("value", type=click.Choice(STATUS_VALUE_TO_CODE_MAP[name], case_sensitive=False))
    @pass_projector
    @pass_output_func
    def _control_cmd(output_func: clitypes.OutputFn, projector: Projector, value: str):
        projector_cmd = getattr(projector, fn_name)
        click.echo(friendly_name, err=True)
        projector_cmd(value)

    _control_cmd.__doc__ = f"{friendly_name}"

    return _control_cmd



for name in STATUS_VALUE_TO_CODE_MAP:
    cli_control.add_command(_make_control_command(name))

if __name__ == "__main__":
    cli()
