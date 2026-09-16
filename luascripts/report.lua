-- Jaymod Lua: !report <player> <reason> -> Discord embed
-- Put the webhook in jaymod/report.cfg (same idea as legacy/report.cfg).
-- Do not put the URL in jaymod.cfg or in this script.
-- Load with: set lua_modules "report.lua"

modname = "report"
version = "1.2"

local REPORT_CFG = "report.cfg"
local EMBED_COLOR = 15158332

local function json_escape(s)
    s = string.gsub(s or "", "\\", "\\\\")
    s = string.gsub(s, "\"", "\\\"")
    s = string.gsub(s, "\n", "\\n")
    s = string.gsub(s, "\r", "\\r")
    s = string.gsub(s, "\t", "\\t")
    return s
end

local function player_name(clientNum)
    local info = et.trap_GetUserinfo(clientNum)
    local name = et.Info_ValueForKey(info, "name")
    if name == nil or name == "" then
        name = et.gentity_get(clientNum, "pers.netname") or "unknown"
    end
    return et.Q_CleanStr(name)
end

local function player_guid(clientNum)
    local info = et.trap_GetUserinfo(clientNum)
    local g = et.Info_ValueForKey(info, "cl_guid")
    if not g or g == "" then
        g = et.Info_ValueForKey(info, "guid")
    end
    if not g or g == "" then
        return "unknown"
    end
    return g
end

local function player_ip(clientNum)
    local info = et.trap_GetUserinfo(clientNum)
    local ip = et.Info_ValueForKey(info, "ip") or ""
    ip = ip:match("^([^:]+)") or ip
    if ip == "" then
        return "unknown"
    end
    return ip
end

local function parse_cfg(text)
    local cfg = { webhook = "", role = "" }
    if not text or text == "" then
        return cfg
    end
    for line in string.gmatch(text, "[^\r\n]+") do
        line = line:gsub("^%s+", ""):gsub("%s+$", "")
        if line ~= "" and not line:match("^#") then
            local k, v = line:match("^(%w+)%s*=%s*(.*)$")
            if k and v then
                cfg[k] = v:gsub("%s+$", "")
            end
        end
    end
    return cfg
end

local function read_via_fs(path)
    local fd, len = et.trap_FS_FOpenFile(path, et.FS_READ)
    if not fd or not len or len < 0 then
        return nil
    end
    local text = et.trap_FS_Read(fd, len) or ""
    et.trap_FS_FCloseFile(fd)
    return text
end

local function read_via_io(path)
    if not io or not io.open then
        return nil
    end
    local f = io.open(path, "r")
    if not f then
        return nil
    end
    local text = f:read("*a") or ""
    f:close()
    return text
end

local function load_report_cfg()
    local game = et.trap_Cvar_Get("fs_game") or "jaymod"
    local text = read_via_fs(REPORT_CFG)
        or read_via_io(game .. "/" .. REPORT_CFG)
        or read_via_io(REPORT_CFG)
    local cfg = parse_cfg(text)
    if cfg.webhook == "" then
        cfg.webhook = et.trap_Cvar_Get("lua_reportWebhook") or ""
    end
    return cfg
end

local function webhook_ok(url)
    return url:match("^https://discord%.com/api/webhooks/")
        or url:match("^https://discordapp%.com/api/webhooks/")
end

local function mention_block(role)
    local tags, ids, seen = {}, {}, {}
    for id in (role or ""):gmatch("%d+") do
        if not seen[id] then
            seen[id] = true
            tags[#tags + 1] = "<@&" .. id .. ">"
            ids[#ids + 1] = '"' .. id .. '"'
        end
    end
    if #tags == 0 then
        return "", '"allowed_mentions":{"parse":[]}'
    end
    return table.concat(tags, " "),
        '"allowed_mentions":{"parse":[],"roles":[' .. table.concat(ids, ",") .. "]}"
end

local function embed_field(name, value, inline)
    return string.format(
        '{"name":"%s","value":"%s","inline":%s}',
        json_escape(name),
        json_escape(value),
        inline and "true" or "false"
    )
end

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)
    et.G_Print("report.lua loaded (webhook from report.cfg)\n")
end

function et_ClientCommand(clientNum, command)
    local arg0 = string.lower(et.trap_Argv(0) or "")
    if arg0 ~= "say" and arg0 ~= "say_team" and arg0 ~= "say_buddy" then
        return 0
    end

    local text = et.ConcatArgs(1) or ""
    local prefix = string.sub(string.lower(text), 1, 7)
    if prefix ~= "!report" then
        return 0
    end

    local rest = string.gsub(text, "^%s*!report%s*", "")
    local target, reason = rest:match("^(%S+)%s+(.+)$")
    if not target or not reason or reason:match("^%s*$") then
        et.trap_SendServerCommand(clientNum, "cpm \"Usage: !report <player> <reason>\"\n")
        return 1
    end

    local accused = et.ClientNumberFromString(target)
    if accused == nil then
        et.trap_SendServerCommand(clientNum, "cpm \"!report: no unique player match.\"\n")
        return 1
    end

    local cfg = load_report_cfg()
    local webhook = cfg.webhook or ""
    if not webhook_ok(webhook) then
        et.trap_SendServerCommand(clientNum, "cpm \"!report is not configured (report.cfg).\"\n")
        et.G_LogPrint("report.lua: report.cfg webhook is empty or invalid\n")
        return 1
    end

    local mention, allowed = mention_block(cfg.role)
    local hostname = et.Q_CleanStr(et.trap_Cvar_Get("sv_hostname") or "ETHost")
    local mapname = et.trap_Cvar_Get("mapname") or "unknown"
    local when = os.date("%Y-%m-%d %H:%M")
    local reporter = player_name(clientNum)
    local accusedName = player_name(accused)
    local desc = hostname .. " · " .. mapname .. " · " .. when

    local fields = table.concat({
        embed_field("Accused", string.format("%s (#%d)", accusedName, accused), true),
        embed_field("Reporter", string.format("%s (#%d)", reporter, clientNum), true),
        embed_field("GUID", "(" .. player_guid(accused) .. ")", false),
        embed_field("IP", "(" .. player_ip(accused) .. ")", false),
        embed_field("Reason", reason, false),
    }, ",")

    local content = ""
    if mention ~= "" then
        content = string.format("\"content\":\"%s\",", json_escape(mention))
    end

    local payload = string.format(
        "{%s\"embeds\":[{\"title\":\"Jaymod report\",\"description\":\"%s\",\"color\":%d,\"fields\":[%s]}],%s}",
        content,
        json_escape(desc),
        EMBED_COLOR,
        fields,
        allowed
    )

    local status, body = et.httpRequest(
        webhook,
        "POST",
        payload,
        { ["Content-Type"] = "application/json" }
    )

    if status == 204 or status == 200 then
        et.trap_SendServerCommand(clientNum, "cpm \"Report sent.\"\n")
        et.G_LogPrint(string.format("report.lua: %s reported %s: %s\n", reporter, accusedName, reason))
    else
        et.trap_SendServerCommand(clientNum, "cpm \"Report failed to send.\"\n")
        et.G_LogPrint(string.format("report.lua: webhook status %s body %s\n", tostring(status), tostring(body)))
    end

    return 1
end
