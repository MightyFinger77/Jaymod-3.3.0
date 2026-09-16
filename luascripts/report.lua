-- Jaymod Lua: !report -> Discord webhook
-- Set lua_reportWebhook to your Discord webhook URL.
-- Load with: set lua_modules "report.lua"

modname = "report"
version = "1.0"

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

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)
    et.G_Print("report.lua loaded\n")
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

    local reason = string.gsub(text, "^%s*!report%s*", "")
    if reason == "" then
        et.trap_SendServerCommand(clientNum, "cpm \"Usage: !report <message>\"\n")
        return 1
    end

    local webhook = et.trap_Cvar_Get("lua_reportWebhook")
    if webhook == nil or webhook == "" then
        et.trap_SendServerCommand(clientNum, "cpm \"!report is not configured (lua_reportWebhook).\"\n")
        et.G_LogPrint("report.lua: lua_reportWebhook is empty\n")
        return 1
    end

    local mapname = et.trap_Cvar_Get("mapname")
    local reporter = player_name(clientNum)
    local payload = string.format(
        "{\"content\":\"**ET report** from **%s** (slot %d) on **%s**:\\n%s\"}",
        json_escape(reporter),
        clientNum,
        json_escape(mapname),
        json_escape(reason)
    )

    local status, body = et.httpRequest(
        webhook,
        "POST",
        payload,
        { ["Content-Type"] = "application/json" }
    )

    if status == 204 or status == 200 then
        et.trap_SendServerCommand(clientNum, "cpm \"Report sent.\"\n")
        et.G_LogPrint(string.format("report.lua: %s reported: %s\n", reporter, reason))
    else
        et.trap_SendServerCommand(clientNum, "cpm \"Report failed to send.\"\n")
        et.G_LogPrint(string.format("report.lua: webhook status %s body %s\n", tostring(status), tostring(body)))
    end

    return 1
end
