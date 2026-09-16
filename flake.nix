{
  description = "nanokvmctl — power/reset/virtual-media/boot control for a Sipeed NanoKVM";

  inputs.nixpkgs.url = "nixpkgs";

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python3;

      nanokvm = python.pkgs.callPackage ./nanokvm.nix { };
      nanokvmctl = python.pkgs.callPackage ./default.nix { inherit nanokvm; };
    in
    {
      packages.${system} = {
        inherit nanokvmctl nanokvm;
        default = nanokvmctl;
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = [
          (python.withPackages (ps: [ nanokvm ]))
          nanokvmctl
          pkgs.socat # bridge a unix-socket-only KVM endpoint to a local TCP port
          pkgs.curl
        ];
        shellHook = ''
          echo "nanokvmctl devshell"
          echo "  nanokvmctl --endpoint https://<kvm-ip> --insecure info"
          echo "  nanokvmctl ... boot ./trampoline-nixos.iso"
        '';
      };
    };
}
