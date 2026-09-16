# Standalone, callPackage-friendly build of the nanokvmctl CLI.
#
# `nanokvm` is injected as an argument (the library it wraps) so the caller
# controls how it's packaged:
#   pkgs.python3Packages.callPackage ./default.nix {
#     nanokvm = pkgs.python3Packages.callPackage ./nanokvm.nix { };
#   }
{
  lib,
  buildPythonApplication,
  hatchling,
  aiohttp,
  nanokvm,
}:
buildPythonApplication {
  pname = "nanokvmctl";
  version = "0.1.0";
  pyproject = true;

  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./nanokvmctl
    ];
  };

  build-system = [ hatchling ];

  dependencies = [
    nanokvm
    aiohttp
  ];

  pythonImportsCheck = [ "nanokvmctl" ];
  doCheck = false;

  meta = {
    description = "Power/reset/virtual-media/boot control for a Sipeed NanoKVM";
    homepage = "https://github.com/warmdarksea/nanokvmctl";
    license = lib.licenses.mit;
    mainProgram = "nanokvmctl";
  };
}
