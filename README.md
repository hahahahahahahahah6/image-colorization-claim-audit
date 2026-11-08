# Documentation claim auditor

An offline, deterministic, standard-library-only CLI for checking claims about
adding colour to a grey still picture against static Python source evidence.
Requires Python 3.9 or newer. No network, telemetry, LLM, or file writes are used.

## Usage

```sh
python3 -m pip install .
image-colorization-claim-audit --version
image-colorization-claim-audit audit . --json
python3 -m image_colorization_claim_audit audit --ignore vendor/ .
image-colorization-claim-audit audit . --fail-on medium --verbose
```

The repository defaults to the current directory. Ignore options accept one
literal relative path prefix each and may be repeated. Root README and Markdown
under docs are checked. Triple backtick fences are excluded; inline code counts
as prose. Claims appearing only in tests have medium severity. Sources are never
executed. Aliases are resolved within individual modules; local function and
class definitions shadow imported names. Cache and virtual environment folders
are skipped. Invalid syntax supplies no evidence.

Exit codes are 0 for PASS, 2 for findings meeting the threshold, and 1 for usage
or IO errors. The default threshold is high. JSON includes an overall verdict
and findings with rule, severity, verdict and message fields. Verbose scope and
per-file decisions go to standard error.

```text
documented-image-colorization-claim-false HIGH
documented-no-image-colorization-claim-false HIGH
documented-image-colorization-claim-false MEDIUM (test fixtures only)
```

## Differentiation

These neighboring auditors respectively check creating new images, removing
noise, adding pixels, and filling missing regions. This auditor checks adding
colour across an existing grey still picture.

```text
image-generation-claim-audit
image-denoising-claim-audit
super-resolution-claim-audit
image-inpainting-claim-audit
```

## Limitations

Static pattern matching is not semantic judgement. Exact case-insensitive
substrings are used, without restatement, stemming, or hyphen normalization.
Denial spans are removed first. Longest-first matching with span blanking makes
each occurrence match once under its longest phrase.

The following video call is deliberately excluded because video is not a still
picture. The generic call on an unrelated object counts because its method name
is shared.

```text
get_video_colorizer(...)
unrelated.colorize(...)
```

These phrases can also describe CSS filter tinting and a color overlay tint.
Both still match, an ambiguity of exact substring matching:

```text
colorize images with a CSS filter
adds color to images as a watermark tint
```

Recognized evidence uses a library factory paired with a transform, a pipeline
paired with processing, a model paired with invocation, a network loader with a
relevant literal paired with forwarding, or a listed generic call. Pairs must
belong to the same resulting object within one module. Bare imports, lone
constructions, strings, comments, unbound references and subprocess commands
supply no evidence. Conversion to grey, noise removal, enlargement, filling,
generation, hue adjustments, masking and detection alone supply no evidence.
Static patterns cannot prove runtime behavior or infer custom implementations.

## Development

```sh
python3 -m unittest discover
python3 -m build
```

Licensed under MIT.
