# Third-Party Notices

Part Pilot includes or is built with third-party software. These components are **not** licensed under the Part Pilot project license. Each third-party component remains governed by its own license terms.

The exact license/copyright texts collected for the locked v1.0.0 dependency graph are stored under `third_party/licenses/`. The application container copies this notice and that directory to `/app/third_party/`.

## Python runtime packages

| Package | Version | License metadata |
| --- | --- | --- |
| `alembic` | `1.19.0` | MIT |
| `annotated-doc` | `0.0.5` | MIT |
| `annotated-types` | `0.8.0` | MIT |
| `anyio` | `4.14.2` | MIT |
| `attrs` | `26.1.0` | MIT |
| `bcrypt` | `4.0.1` | Apache License, Version 2.0 |
| `certifi` | `2026.7.22` | MPL-2.0 |
| `cffi` | `2.1.1` | MIT-0 |
| `click` | `8.4.2` | BSD-3-Clause |
| `cryptography` | `50.0.0` | Apache-2.0 OR BSD-3-Clause |
| `fastapi` | `0.141.1` | MIT |
| `greenlet` | `3.5.4` | MIT AND PSF-2.0 |
| `h11` | `0.16.0` | MIT |
| `httpcore` | `1.0.9` | BSD-3-Clause |
| `httptools` | `0.8.0` | MIT |
| `httpx` | `0.28.1` | BSD-3-Clause |
| `httpx-sse` | `0.4.3` | MIT |
| `idna` | `3.18` | BSD-3-Clause |
| `jsonschema` | `4.26.0` | MIT |
| `jsonschema-specifications` | `2025.9.1` | MIT |
| `Mako` | `1.4.1` | MIT |
| `MarkupSafe` | `3.0.3` | BSD-3-Clause |
| `mcp` | `1.27.2` | MIT |
| `passlib` | `1.7.4` | BSD |
| `pillow` | `11.3.0` | MIT-CMU |
| `pycparser` | `3.0` | BSD-3-Clause |
| `pydantic` | `2.13.4` | MIT |
| `pydantic-settings` | `2.15.0` | MIT |
| `pydantic_core` | `2.46.4` | MIT |
| `PyJWT` | `2.13.0` | MIT |
| `python-dotenv` | `1.2.2` | BSD-3-Clause |
| `python-multipart` | `0.0.32` | Apache-2.0 |
| `PyYAML` | `6.0.3` | MIT |
| `referencing` | `0.37.0` | MIT |
| `rpds-py` | `2026.6.3` | MIT |
| `SQLAlchemy` | `2.0.51` | MIT |
| `sse-starlette` | `3.4.8` | BSD-3-Clause |
| `starlette` | `1.4.1` | BSD-3-Clause |
| `typing-inspection` | `0.4.2` | MIT |
| `typing_extensions` | `4.16.0` | PSF-2.0 |
| `uvicorn` | `0.52.1` | BSD-3-Clause |
| `uvloop` | `0.22.1` | MIT License |
| `watchfiles` | `1.2.0` | MIT |
| `websockets` | `17.0.1` | BSD-3-Clause |

## Frontend dependency lock

The frontend is built with the exact `frontend/package-lock.json` committed for v1.0.0. Build-time dependencies are listed here even when their code is not present in the final browser bundle.

| Package | Version | License metadata |
| --- | --- | --- |
| `@emnapi/core` | `2.0.0-alpha.3` | MIT |
| `@emnapi/runtime` | `2.0.0-alpha.3` | MIT |
| `@emnapi/wasi-threads` | `2.0.1` | MIT |
| `@napi-rs/wasm-runtime` | `1.2.1` | MIT |
| `@oxc-project/types` | `0.142.0` | MIT |
| `@rolldown/binding-android-arm64` | `1.2.1` | MIT |
| `@rolldown/binding-darwin-arm64` | `1.2.1` | MIT |
| `@rolldown/binding-darwin-x64` | `1.2.1` | MIT |
| `@rolldown/binding-freebsd-x64` | `1.2.1` | MIT |
| `@rolldown/binding-linux-arm-gnueabihf` | `1.2.1` | MIT |
| `@rolldown/binding-linux-arm64-gnu` | `1.2.1` | MIT |
| `@rolldown/binding-linux-arm64-musl` | `1.2.1` | MIT |
| `@rolldown/binding-linux-ppc64-gnu` | `1.2.1` | MIT |
| `@rolldown/binding-linux-s390x-gnu` | `1.2.1` | MIT |
| `@rolldown/binding-linux-x64-gnu` | `1.2.1` | MIT |
| `@rolldown/binding-linux-x64-musl` | `1.2.1` | MIT |
| `@rolldown/binding-openharmony-arm64` | `1.2.1` | MIT |
| `@rolldown/binding-wasm32-wasi` | `1.2.1` | MIT |
| `@rolldown/binding-win32-arm64-msvc` | `1.2.1` | MIT |
| `@rolldown/binding-win32-x64-msvc` | `1.2.1` | MIT |
| `@rolldown/pluginutils` | `1.0.1` | MIT |
| `@tybys/wasm-util` | `0.10.3` | MIT |
| `@types/react` | `19.2.17` | MIT |
| `@types/react-dom` | `19.2.3` | MIT |
| `@typescript/typescript-aix-ppc64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-darwin-arm64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-darwin-x64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-freebsd-arm64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-freebsd-x64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-arm` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-arm64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-loong64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-mips64el` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-ppc64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-riscv64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-s390x` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-linux-x64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-netbsd-arm64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-netbsd-x64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-openbsd-arm64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-openbsd-x64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-sunos-x64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-win32-arm64` | `7.0.2` | Apache-2.0 |
| `@typescript/typescript-win32-x64` | `7.0.2` | Apache-2.0 |
| `@vitejs/plugin-react` | `6.0.5` | MIT |
| `cookie` | `1.1.1` | MIT |
| `csstype` | `3.2.3` | MIT |
| `detect-libc` | `2.1.2` | Apache-2.0 |
| `fdir` | `6.5.0` | MIT |
| `fsevents` | `2.3.3` | MIT |
| `lightningcss` | `1.33.0` | MPL-2.0 |
| `lightningcss-android-arm64` | `1.33.0` | MPL-2.0 |
| `lightningcss-darwin-arm64` | `1.33.0` | MPL-2.0 |
| `lightningcss-darwin-x64` | `1.33.0` | MPL-2.0 |
| `lightningcss-freebsd-x64` | `1.33.0` | MPL-2.0 |
| `lightningcss-linux-arm-gnueabihf` | `1.33.0` | MPL-2.0 |
| `lightningcss-linux-arm64-gnu` | `1.33.0` | MPL-2.0 |
| `lightningcss-linux-arm64-musl` | `1.33.0` | MPL-2.0 |
| `lightningcss-linux-x64-gnu` | `1.33.0` | MPL-2.0 |
| `lightningcss-linux-x64-musl` | `1.33.0` | MPL-2.0 |
| `lightningcss-win32-arm64-msvc` | `1.33.0` | MPL-2.0 |
| `lightningcss-win32-x64-msvc` | `1.33.0` | MPL-2.0 |
| `nanoid` | `3.3.16` | MIT |
| `picocolors` | `1.1.1` | ISC |
| `picomatch` | `4.0.5` | MIT |
| `postcss` | `8.5.25` | MIT |
| `react` | `19.2.8` | MIT |
| `react-dom` | `19.2.8` | MIT |
| `react-router` | `7.18.2` | MIT |
| `react-router-dom` | `7.18.2` | MIT |
| `rolldown` | `1.2.1` | MIT |
| `scheduler` | `0.27.0` | MIT |
| `set-cookie-parser` | `2.7.2` | MIT |
| `source-map-js` | `1.2.1` | BSD-3-Clause |
| `tinyglobby` | `0.2.17` | MIT |
| `tslib` | `2.8.1` | 0BSD |
| `typescript` | `7.0.2` | Apache-2.0 |
| `vite` | `8.2.0` | MIT |

## Debian/Python base image

The runtime is based on the pinned multi-architecture Python 3.12.13 slim image. Debian system packages retain their own licenses. Their exact copyright files are preserved in the runtime image under `/usr/share/doc/*/copyright` and are also collected in `third_party/licenses/debian.txt`.

The locked image contains 61 Debian source package/version pairs. Exact corresponding-source download URLs, sizes, and SHA-256 hashes are recorded in `third_party/debian-source-files.tsv`. The tag workflow publishes those source archives in a companion GHCR source image at the same version as Part Pilot.

Companion source image target:

```text
ghcr.io/devanshtangri/part-pilot-source:<version>
```

The source image is data-only and contains `/sources/` with the exact Debian source archives plus manifests/notices. It is intended to provide network-accessible corresponding source for redistributed GPL/LGPL-covered base-image components. Package-specific license terms remain authoritative.

## MPL-covered components

`certifi` is present in the Python runtime under MPL-2.0; its source-form Python files and license are present in the application image. The locked frontend build graph contains MPL-2.0 `lightningcss` packages as build dependencies; their license texts are included in the frontend corpus even though the package implementation is not copied into the final browser bundle.

## No relicensing of third-party software

Any Part Pilot project license applies only to Part Pilot original code and assets. It does not replace, restrict, or supersede the licenses of the third-party components identified here.
