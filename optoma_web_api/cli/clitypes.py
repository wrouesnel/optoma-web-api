import functools
import io
import json
from gettext import gettext as _
from gettext import ngettext
from typing import Any, Callable, Dict, List, Optional

import click
import click.shell_completion
import ruamel.yaml
import ruamel.yaml.scalarstring
import toml

OutputFn = Callable[[Any], str]


def _output_yaml(obj) -> str:
    yaml = ruamel.yaml.YAML(typ="rt")
    yaml.default_flow_style = False
    # Force strings to format as blocks
    ruamel.yaml.scalarstring.walk_tree(obj)
    bio = io.BytesIO()
    yaml.dump(obj, bio)
    return bio.getvalue().decode("utf8")


class OutputFormat(click.ParamType):
    """Output format allows a selection of a number of equivalent key-value renderers"""

    name = "output-format"

    SUPPORTED_FORMATS: Dict[str, OutputFn] = {
        "json": functools.partial(json.dumps, sort_keys=True, indent=True),
        "yaml": _output_yaml,
        "yml": _output_yaml,
        "toml": toml.dumps,
    }

    def get_metavar(self, param: "click.Parameter") -> str:
        choices_str = "|".join(self.SUPPORTED_FORMATS)

        # Use curly braces to indicate a required argument.
        if param.required and param.param_type_name == "argument":
            return f"{{{choices_str}}}"

        # Use square braces to indicate an option or optional argument.
        return f"[{choices_str}]"

    def get_missing_message(self, param: "click.Parameter") -> str:
        return _("Choose from:\n\t{SUPPORTED_FORMATS}").format(
            choices=",\n\t".join(self.SUPPORTED_FORMATS)
        )

    def convert(
        self,
        value: Any,
        param: Optional["click.Parameter"],
        ctx: Optional["click.Context"],
    ) -> Any:
        # Match through normalization and case sensitivity
        # first do token_normalize_func, then lowercase
        # preserve original `value` to produce an accurate message in
        # `self.fail`
        normed_value = value
        normed_choices = {
            choice: value for choice, value in self.SUPPORTED_FORMATS.items()
        }

        if ctx is not None and ctx.token_normalize_func is not None:
            normed_value = ctx.token_normalize_func(value)
            normed_choices = {
                ctx.token_normalize_func(normed_choice): original
                for normed_choice, original in normed_choices.items()
            }

        normed_value = normed_value.casefold()
        normed_choices = {
            normed_choice.casefold(): original
            for normed_choice, original in normed_choices.items()
        }

        if normed_value in normed_choices:
            return normed_choices[normed_value]

        choices_str = ", ".join(map(repr, self.SUPPORTED_FORMATS))
        self.fail(
            ngettext(
                "{value!r} is not {choice}.",
                "{value!r} is not one of {choices}.",
                len(self.SUPPORTED_FORMATS),
            ).format(value=value, choice=choices_str, choices=choices_str),
            param,
            ctx,
        )

    def __repr__(self) -> str:
        return f"OutputFormat()"

    def shell_complete(
        self, ctx: "click.Context", param: "click.Parameter", incomplete: str
    ) -> List["click.shell_completion.CompletionItem"]:
        """Complete choices that start with the incomplete value.

        :param ctx: Invocation context for this command.
        :param param: The parameter that is requesting completion.
        :param incomplete: Value being completed. May be empty.

        .. versionadded:: 8.0
        """
        from click.shell_completion import CompletionItem

        str_choices = map(str, self.SUPPORTED_FORMATS)

        incomplete = incomplete.lower()
        matched = (c for c in str_choices if c.lower().startswith(incomplete))

        return [CompletionItem(c) for c in matched]
