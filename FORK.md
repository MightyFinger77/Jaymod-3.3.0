# Fork notes

**Jaymod 3.1.0** (mod / pk3 version) is published from [MightyFinger77/Jaymod-3.3.0](https://github.com/MightyFinger77/Jaymod-3.3.0). It forks [RngesusSolutions/jaymod2.2.0](https://github.com/RngesusSolutions/jaymod2.2.0) (Jaymod 2.3.0), itself a maintenance of official 2.2.0.

Lineage: **2.2.0** → **2.3.0** → **3.0.0** (Lua + 64-bit ETL) → **3.1.0** (EnhMod-in-qagame, widescreen HUD, mapvote READY, `g_oss`).

User-facing docs:

- [Server install](docs/server.md) — install, `g_oss`, map voting, EnhMod, Omni-bot
- [Lua](docs/lua.md)
- [Changelog](docs/changelog.md)
- [Cvars](docs/cvar.md)
- [Build](docs/build.md)

## License

Lua bindings implement the [published Legacy Lua API](https://etlegacy-lua-docs.readthedocs.io/en/latest/). They are **not** a copy of ET: Legacy’s GPLv3 `g_lua.c`. Jaymod remains Apache 2.0 plus id Software’s original terms.
