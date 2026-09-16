#include <bgame/impl.h>

namespace cmd {

///////////////////////////////////////////////////////////////////////////////

NextMap::NextMap()
    : AbstractBuiltin( "nextmap" )
{
    __usage << xvalue( "!" + _name );
    __descr << "Ends the current map and advances to the next map.";
}

///////////////////////////////////////////////////////////////////////////////

NextMap::~NextMap()
{
}

///////////////////////////////////////////////////////////////////////////////

AbstractCommand::PostAction
NextMap::doExecute( Context& txt )
{
    if (txt._args.size() > 1)
        return PA_USAGE;

    switch ((gamestate_t)cvars::gameState.ivalue) {
        case GS_INTERMISSION:
            /* Force end vote / intermission (!nextmap). READY also does this. */
            level.ref_allready = qtrue;
            level.exitLevelTime = 0;
            ExitLevel();
            break;

        case GS_WARMUP_COUNTDOWN:
        case GS_WARMUP:
            if (g_gametype.integer == GT_WOLF_MAPVOTE) {
                BeginIntermission();
                break;
            }
            ExitLevel();
            break;

        default:
            G_Script_ScriptEvent( level.gameManager, "trigger", "timelimit_hit" );
            LogExit( "!nextmap." );
            break;
    }

    return PA_NONE;
}

///////////////////////////////////////////////////////////////////////////////

} // namespace cmd
