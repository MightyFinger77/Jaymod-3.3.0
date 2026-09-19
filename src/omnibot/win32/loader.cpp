#include <bgame/impl.h>
#include <omnibot/common/BotExports.h>
#include <windows.h>
#include <tlhelp32.h>

extern bool   g_IsOmnibotLoaded;
extern string g_OmnibotLibPath;

///////////////////////////////////////////////////////////////////////////////

namespace {
    const char* const __LIB_SUFFIX = ".dll";
    const char* const __OMNI_DIR   = "omni-bot";
    const char* const __OMNI_LOG   = "OMNIBOT:";
    const char        __PATHSEP    = '\\';

    set<string>  __dirSet;
    list<string> __dirList;
    HINSTANCE    __handle = NULL;

    void addDirectory( string dir ) {
        // skip if already present
        if (!__dirSet.insert( dir ).second)
            return;

        __dirList.push_back( dir );
    }
}

///////////////////////////////////////////////////////////////////////////////

static const char*
win32LoadError()
{
    static char buf[256];
    const DWORD code = GetLastError();
    buf[0] = '\0';
    FormatMessageA( FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL, code, 0, buf, sizeof(buf), NULL );
    for ( char* p = buf; *p; ++p ) {
        if (*p == '\r' || *p == '\n')
            *p = ' ';
    }
    return va( "%lu %s", (unsigned long)code, buf );
}

///////////////////////////////////////////////////////////////////////////////

static const char *
omniBotDllBasename()
{
#if defined(_WIN64) || defined(__x86_64__) || defined(__amd64__)
    return "omnibot_et_x64.dll";
#else
    return "omnibot_et.dll";
#endif
}

static HMODULE
FindOmnibotModule()
{
    HMODULE h = GetModuleHandleA( omniBotDllBasename() );
    if (h)
        return h;

    h = GetModuleHandleA( "omnibot_et_x64.dll" );
    if (h)
        return h;
    h = GetModuleHandleA( "omnibot_et.dll" );
    if (h)
        return h;

    if (!g_OmnibotLibPath.empty()) {
        string p = g_OmnibotLibPath;
        for ( size_t i = 0; i < p.size(); ++i ) {
            if (p[i] == '/')
                p[i] = '\\';
        }
        h = GetModuleHandleA( p.c_str() );
        if (h)
            return h;
        for ( size_t i = 0; i < p.size(); ++i ) {
            if (p[i] == '\\')
                p[i] = '/';
        }
        h = GetModuleHandleA( p.c_str() );
        if (h)
            return h;
    }

    HANDLE snap = CreateToolhelp32Snapshot( TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId() );
    if (snap == INVALID_HANDLE_VALUE)
        return NULL;

    MODULEENTRY32W me;
    memset( &me, 0, sizeof(me) );
    me.dwSize = sizeof(me);
    h = NULL;
    if (Module32FirstW( snap, &me )) {
        do {
            if (!_wcsicmp( me.szModule, L"omnibot_et_x64.dll" )
                || !_wcsicmp( me.szModule, L"omnibot_et.dll" )) {
                h = me.hModule;
                break;
            }
        } while (Module32NextW( snap, &me ));
    }
    CloseHandle( snap );
    return h;
}

/* LoadLibrary bumps the refcount if the dll is already mapped. One FreeLibrary
 * is not enough after a map change. Walk the count down to zero. */
static int
Omnibot_DropModule()
{
    int n = 0;
    for ( ; n < 64; ++n ) {
        HMODULE h = FindOmnibotModule();
        if (!h)
            break;
        if (!FreeLibrary( h )) {
            G_Printf( "%s FreeLibrary failed (%s)\n", __OMNI_LOG, win32LoadError() );
            break;
        }
    }
    __handle = NULL;
    return n;
}

///////////////////////////////////////////////////////////////////////////////

eomnibot_error
Omnibot_LoadLibrary( const int version, const char* const libbase, const char* const customdir )
{
    G_Printf( "%s loader version 0.82\n", __OMNI_LOG );

    __dirSet.clear();
    __dirList.clear();

    // ETL Win64 ships omnibot_et_x64.dll. omnibot_et.dll is 32-bit and cannot
    // be loaded by a 64-bit qagame (LoadLibrary error 193).
    vector<string> libnames;
#if defined(_WIN64) || defined(__x86_64__) || defined(__amd64__)
    libnames.push_back( string(libbase) + "_x64" + __LIB_SUFFIX );
#endif
    libnames.push_back( string(libbase) + __LIB_SUFFIX );

    // prepare list of path names
    set<string>   dirSet;
    list<string*> dirList;

    // add custom dir
    if (customdir && customdir[0])
        addDirectory( customdir );

    // add fs_homepath based dir
    {
        char buffer[1024];
        trap_Cvar_VariableStringBuffer( "fs_homepath", buffer, sizeof(buffer) );
        if (*buffer) {
            ostringstream path;
            path << buffer << __PATHSEP << __OMNI_DIR;
            addDirectory( path.str() );
        }
    }

    // add fs_basepath based dir
    {
        char buffer[1024];
        trap_Cvar_VariableStringBuffer( "fs_basepath", buffer, sizeof(buffer) );
        if (*buffer) {
            ostringstream path;
            path << buffer << __PATHSEP << __OMNI_DIR;
            addDirectory( path.str() );
        }
    }

    // add "ProgramFiles" based dir
    {
        const char* pf = getenv( "ProgramFiles" );
        if (pf && *pf) {
            ostringstream path;
            path << pf << __PATHSEP << __OMNI_DIR;
            addDirectory( path.str() );
        }
    }

    // add special zero-length string for final try
    addDirectory( "" );

    // print search path
    G_Printf( "%s search path:\n", __OMNI_LOG );

    const list<string>::iterator end = __dirList.end();
    for ( list<string>::iterator it = __dirList.begin(); it != end; it++ ) {
        const string& dir = *it;

        if (dir.length())
            G_Printf( "    %s\n", dir.c_str() );
        else
            G_Printf( "    <SYSTEM-LOADER>\n" );
    }

    // A leftover omnibot_et_x64 from the previous qagame still holds
    // IEngineInterface pointers into unmapped memory. Do not pfnShutdown
    // that copy from this qagame - just drop the mapping, then LoadLibrary
    // a fresh instance and re-resolve exports.
    {
        HMODULE preexisting = FindOmnibotModule();
        if (preexisting) {
            char modpath[MAX_PATH];
            modpath[0] = '\0';
            GetModuleFileNameA( preexisting, modpath, sizeof(modpath) );
            G_Printf( "%s in-process dll still mapped '%s' - unloading before reload\n",
                __OMNI_LOG, modpath[0] ? modpath : omniBotDllBasename() );
            const int dropped = Omnibot_DropModule();
            G_Printf( "%s force-unloaded previous dll (%d FreeLibrary)\n",
                __OMNI_LOG, dropped );
            memset( &g_BotFunctions, 0, sizeof(g_BotFunctions) );
            if (FindOmnibotModule())
                G_Printf( "%s dll still mapped after force-unload (pinned?). Fresh LoadLibrary will reuse it.\n",
                    __OMNI_LOG );
        }
    }

    for ( list<string>::iterator it = __dirList.begin(); it != end; it++ ) {
        const string& dir = *it;

        string name = dir;
        if (name.length() && name[ name.length()-1 ] != __PATHSEP)
            name += __PATHSEP;

        for ( size_t li = 0; li < libnames.size(); ++li ) {
            string tryname = name + libnames[li];
            const bool absPath = (tryname.length() >= 2 && tryname[1] == ':')
                || (tryname.length() >= 2 && tryname[0] == '\\');
            if (absPath)
                __handle = LoadLibraryExA( tryname.c_str(), NULL, LOAD_WITH_ALTERED_SEARCH_PATH );
            else
                __handle = LoadLibraryA( tryname.c_str() );

            if (__handle) {
                G_Printf( "%s load '%s': success\n", __OMNI_LOG, tryname.c_str() );
                name = tryname;
                break;
            }

            G_Printf( "%s load '%s': failure (%s)\n",
                __OMNI_LOG, tryname.c_str(), win32LoadError() );
        }

        if (!__handle)
            continue;

        // success, update buffer indicating bot path
        g_OmnibotLibPath = name;
        break;
    }

    if (!__handle)
        return BOT_ERROR_CANTLOADDLL;

    // check proper dll and initialize it
    pfnGetFunctionsFromDLL pfnGetBotFuncs = 0;
    memset( &g_BotFunctions, 0, sizeof(g_BotFunctions) );

    pfnGetBotFuncs = (pfnGetFunctionsFromDLL)GetProcAddress( __handle, "ExportBotFunctionsFromDLL" );
    G_Printf( "%s address-lookup: %s\n", __OMNI_LOG, pfnGetBotFuncs ? "success" : "failure" );
    if (!pfnGetBotFuncs) {
        G_Printf( "%s GetProcAddress failed\n", __OMNI_LOG );
        Omnibot_FreeLibrary();
        return BOT_ERROR_CANTGETBOTFUNCTIONS;
    }

    eomnibot_error oe = pfnGetBotFuncs( &g_BotFunctions, sizeof(g_BotFunctions) );
    G_Printf( "%s pfnGetBotFuncs: %s\n", __OMNI_LOG, oe == BOT_ERROR_NONE ? "success" : "failure" );
    if (oe != BOT_ERROR_NONE) {
        G_Printf("%s pfnGetBotFuncs failed - %s\n", __OMNI_LOG, Omnibot_ErrorString(oe));
        Omnibot_FreeLibrary();
        return oe;
    }

    oe = Omnibot_GuardedInitialize( version );
    if (oe != BOT_ERROR_NONE || !g_IsOmnibotLoaded) {
        G_Printf( "%s initialization: failure - unloading dll so the next map can retry\n", __OMNI_LOG );
        Omnibot_FreeLibrary();
        return oe != BOT_ERROR_NONE ? oe : BOT_ERROR_CANTINITBOT;
    }

    G_Printf( "%s initialization: success\n", __OMNI_LOG );
    return oe;
}

///////////////////////////////////////////////////////////////////////////////

void
Omnibot_FreeLibrary()
{
    if (__handle) {
        FreeLibrary( __handle );
        __handle = NULL;
    }

    const int dropped = Omnibot_DropModule();
    if (dropped)
        G_Printf( "%s dropped in-process dll (%d extra FreeLibrary)\n", __OMNI_LOG, dropped );

    memset( &g_BotFunctions, 0, sizeof(g_BotFunctions) );

    Bot_ClearVisibleInterface();

    delete g_InterfaceFunctions;
    g_InterfaceFunctions = 0;

    g_IsOmnibotLoaded = false;
}
