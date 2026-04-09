from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Homebrew formula for kotlineer.")
    parser.add_argument("--version", required=True, help="Package version.")
    parser.add_argument("--url", required=True, help="Source tarball URL.")
    parser.add_argument("--sha256", required=True, help="SHA256 of the source tarball.")
    parser.add_argument("--homepage", required=True, help="Project homepage.")
    parser.add_argument("--python-formula", required=True, help="Homebrew Python formula name.")
    parser.add_argument("--output", required=True, help="Output formula path.")
    return parser.parse_args()


def render_formula(version: str, url: str, sha256: str, homepage: str, python_formula: str) -> str:
    return f'''class Kotlineer < Formula
  include Language::Python::Virtualenv

  desc "Lightweight Python wrapper around JetBrains kotlin-lsp"
  homepage "{homepage}"
  url "{url}"
  sha256 "{sha256}"

  depends_on "{python_formula}"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "{version}", shell_output("#{{bin}}/kotlineer --version")
    assert_predicate bin/"kotlineer-mcp", :exist?
  end
end
'''


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_formula(
            version=args.version,
            url=args.url,
            sha256=args.sha256,
            homepage=args.homepage,
            python_formula=args.python_formula,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
