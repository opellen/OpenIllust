"""campaign.py - load and minimally validate a campaign.yaml contract.

Shared by qc_svg.py, svg_normalize.py, and make_sheet_guide.py so that a
campaign's palette/canvas/QC-threshold/prompt values can be wired in via
`--campaign <path>` instead of being hardcoded per script.

See references/campaign-schema.md for the full schema. This module
does NOT fully validate against that schema -- it only checks the handful
of keys every consumer needs to exist before it can do anything useful
(name, canvas, palette.allowed). Individual scripts are responsible for
validating/defaulting the additional keys they each read (stroke, qc,
normalize, prompt, ...), since a campaign is allowed to omit keys that a
particular script doesn't need (schema section "Rules": "Unknown extra
keys are allowed; consumers read what they know").

Import cost: importing this module requires PyYAML. Callers that only use
--campaign optionally should import this module lazily (inside the
`if args.campaign:` branch) so that the legacy, no-campaign code path never
requires PyYAML to be installed.
"""

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment issue, not logic
    raise ImportError(
        "campaign.py requires PyYAML to load campaign.yaml files "
        "(pip install pyyaml, or see templates/skills/openillust/requirements.txt)"
    ) from exc


class CampaignError(ValueError):
    """Raised when a campaign.yaml file cannot be read/parsed, or fails the
    minimal required-key validation performed by load_campaign()."""


def load_campaign(path):
    """Load and minimally validate a campaign.yaml file.

    Required keys (raise CampaignError with a clear message if absent):
      - name
      - canvas
      - palette.allowed (a non-empty list)

    Returns the parsed dict as-is otherwise. Unknown/extra keys, and keys
    required only by specific scripts (stroke, qc, normalize, prompt, ...),
    are intentionally NOT validated here -- see module docstring.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        raise CampaignError("could not read campaign file %r: %s" % (str(path), exc)) from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise CampaignError("campaign file %r is not valid YAML: %s" % (str(path), exc)) from exc

    if not isinstance(data, dict):
        raise CampaignError(
            "campaign file %r must be a YAML mapping at the top level (got %s)"
            % (str(path), type(data).__name__)
        )

    if not data.get("name"):
        raise CampaignError("campaign file %r is missing required key 'name'" % str(path))

    if data.get("canvas") in (None, ""):
        raise CampaignError("campaign file %r is missing required key 'canvas'" % str(path))

    palette = data.get("palette")
    if not isinstance(palette, dict) or not palette.get("allowed"):
        raise CampaignError(
            "campaign file %r is missing required key 'palette.allowed' "
            "(must be a non-empty list of hex colors)" % str(path)
        )

    return data
