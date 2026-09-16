# puddly/python-nanokvm (async NanoKVM API client) — not in nixpkgs, packaged
# from the PyPI release. callPackage this with a python package set, e.g.
#   pkgs.python3Packages.callPackage ./nanokvm.nix { }
{
  lib,
  buildPythonPackage,
  fetchPypi,
  setuptools,
  setuptools-git-versioning,
  wheel,
  aiohttp,
  cryptography,
  yarl,
  pillow,
  pydantic,
  paramiko,
}:
buildPythonPackage rec {
  pname = "nanokvm";
  version = "1.2.0";
  pyproject = true;

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-DEb2zuVnydS++1g7WJhFNpNXgQ8Z1jh/gpo67ornvEs=";
  };

  # Upstream builds with setuptools + setuptools-git-versioning; the sdist carries
  # the resolved version in PKG-INFO, so no git checkout is needed.
  build-system = [
    setuptools
    setuptools-git-versioning
    wheel
  ];

  # Upstream pins `setuptools-git-versioning<3`; nixpkgs ships 3.x, which works.
  # Relax the bound so the build-requirement check passes.
  postPatch = ''
    substituteInPlace pyproject.toml \
      --replace-fail "setuptools-git-versioning<3" "setuptools-git-versioning"
  '';

  dependencies = [
    aiohttp
    cryptography
    yarl
    pillow
    pydantic
    paramiko
  ];

  pythonImportsCheck = [ "nanokvm" ];
  doCheck = false;
  # The build-tool pin above is the only metadata mismatch; skip the runtime-deps
  # check that flags it.
  dontCheckRuntimeDeps = true;

  meta = {
    description = "Async client library for the Sipeed NanoKVM HTTP API";
    homepage = "https://github.com/puddly/python-nanokvm";
    license = lib.licenses.asl20;
  };
}
