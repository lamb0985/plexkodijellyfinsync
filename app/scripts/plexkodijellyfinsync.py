from sync_shared import *
from sync_fetch import fetch_items
from sync_logic import sync_logic
from sync_setters import sync_items
from sync_reporting import print_paths, print_sync_comparison, print_sync_results

def main():
    try:
        load_dotenv("/config/.env")

        plex, kodi_db, jellyfin = welcome("/config/.env")

        with console.status("[bold green]Fetching initial resume items...[/bold green]"):
            plex_items = fetch_items(
                "plex",
                plex=plex,
                plex_media_root=PLEX_MEDIA_ROOT
            )
            kodi_items = fetch_items(
                "kodi",
                kodi_db=kodi_db,
                kodi_media_root=KODI_MEDIA_ROOT
            )
            jellyfin_items = fetch_items(
                "jellyfin",
                jellyfin=jellyfin,
                jellyfin_media_root=JELLYFIN_MEDIA_ROOT
            )

        print_paths(plex_items, kodi_items, jellyfin_items)
        print_sync_comparison(plex_items, kodi_items, jellyfin_items)

        parser = argparse.ArgumentParser(
            description="Sync playback progress across Plex, Kodi, and Jellyfin."
        )
        parser.add_argument(
            "-fetched",
            "--fetched",
            action="store_true",
            help="Show items fetched during fallback lookups."
        )
        args = parser.parse_args()

        # Determine sync actions
        actions, _ = sync_logic(
            plex_items,
            kodi_items,
            jellyfin_items,
            plex,
            kodi_db,
            jellyfin,
            plex_media_root=PLEX_MEDIA_ROOT,
            kodi_media_root=KODI_MEDIA_ROOT,
            jellyfin_media_root=JELLYFIN_MEDIA_ROOT,
            show_fetched=args.fetched,
        )

        # Apply sync changes
        successful_actions = sync_items(
            sync_instructions=actions,
            plex=plex,
            kodi_db=kodi_db,
            jellyfin=jellyfin,
        )

        # IMPORTANT:
        # Fetch everything again after updates so the JSON represents
        # the actual final state, not the planned state.
        with console.status("[bold green]Refreshing final sync state...[/bold green]"):
            final_plex_items = fetch_items(
                "plex",
                plex=plex,
                plex_media_root=PLEX_MEDIA_ROOT
            )
            final_kodi_items = fetch_items(
                "kodi",
                kodi_db=kodi_db,
                kodi_media_root=KODI_MEDIA_ROOT
            )
            final_jellyfin_items = fetch_items(
                "jellyfin",
                jellyfin=jellyfin,
                jellyfin_media_root=JELLYFIN_MEDIA_ROOT
            )

        # Rebuild state from real platform values
        _, final_sync_state = sync_logic(
            final_plex_items,
            final_kodi_items,
            final_jellyfin_items,
            plex,
            kodi_db,
            jellyfin,
            plex_media_root=PLEX_MEDIA_ROOT,
            kodi_media_root=KODI_MEDIA_ROOT,
            jellyfin_media_root=JELLYFIN_MEDIA_ROOT,
            show_fetched=False,
        )

        # Save actual post-sync state
        if successful_actions == len(actions):
            save_sync_state(final_sync_state)
        else:
            console.print("[yellow]⚠️ Some sync actions failed; keeping the previous state for retry.[/yellow]")

        # Print results using refreshed data
        print_sync_results(
            final_plex_items,
            final_kodi_items,
            final_jellyfin_items,
            actions
        )

        console.print(
            "[green]🏁 Sync Completed 🏁[/]",
            justify="center"
        )

    except KeyboardInterrupt:
        console.print("[yellow]Interrupted by user[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Fatal error: {e}[/red]")
        traceback.print_exc()


if __name__ == "__main__":
    main()
