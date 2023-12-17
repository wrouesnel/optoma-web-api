import datetime
import logging
import sys
import time
from typing import Any, Callable

import click
import pyrfc3339
from click.decorators import pass_meta_key
from tzlocal import get_localzone

from optoma_web_api import Projector
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


@cli.command("power")
@click.argument("power_state", type=click.Choice(("on", "off"), case_sensitive=False))
@pass_projector
@pass_output_func
def cli_power(output_func: clitypes.OutputFn, projector: Projector, power_state: str):
    """Send projector power command"""
    match power_state:
        case "on":
            click.echo("Power On", err=True)
            projector.power_on()
        case "off":
            click.echo("Power Off", err=True)
            projector.power_off()

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

if __name__ == "__main__":
    cli()
