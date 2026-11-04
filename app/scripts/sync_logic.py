from sync_shared import *
from sync_fetch import fetch_items


PLATFORMS = ("plex", "kodi", "jellyfin")
ID_FIELDS = {"plex": "ratingKey", "kodi": "idFile", "jellyfin": "id"}


def sync_logic(
    plex_items,
    kodi_items,
    jellyfin_items,
    plex,
    kodi_db,
    jellyfin,
    plex_media_root=None,
    kodi_media_root=None,
    jellyfin_media_root=None,
    show_fetched=False,
):
    previous_sync_state = load_sync_state() or {}
    updated_sync_state = {}
    sync_actions = []
    fetched_items_report = {platform: {} for platform in PLATFORMS}
    items_by_platform = {
        "plex": plex_items,
        "kodi": kodi_items,
        "jellyfin": jellyfin_items,
    }
    fallback_args = {
        "plex": {"plex": plex, "plex_media_root": plex_media_root},
        "kodi": {"kodi_db": kodi_db, "kodi_media_root": kodi_media_root},
        "jellyfin": {"jellyfin": jellyfin, "jellyfin_media_root": jellyfin_media_root},
    }

    # Completed items disappear from resume feeds. Look up previously active
    # paths by exact path to detect watched and cleared bookmarks.
    previous_active_paths = {
        path for path, entry in previous_sync_state.items()
        if isinstance(entry, dict) and any(
            (entry.get(platform) or {}).get("resume", 0) or
            (entry.get(platform) or {}).get("status") == "in_progress"
            for platform in PLATFORMS
        )
    }
    all_rel_paths = set().union(*(items.keys() for items in items_by_platform.values()))
    all_rel_paths |= previous_active_paths

    for rel_path in sorted(all_rel_paths):
        previous_entry = previous_sync_state.get(rel_path, {})

        # Preserve the original per-platform fallback methods and full item
        # dictionaries; setters need IDs such as Kodi idMovie/idEpisode.
        with console.status("[bold green]Fetching fallback items...[/bold green]"):
            for platform in PLATFORMS:
                if rel_path in items_by_platform[platform]:
                    continue
                fetched = fetch_items(
                    platform, target_rel_path=rel_path, **fallback_args[platform]
                )
                item = fetched.get(rel_path)
                if item:
                    items_by_platform[platform][rel_path] = item
                    fetched_items_report[platform][rel_path] = item
                else:
                    console.print(f"[red]Unable to fallback fetch![/red] {platform}: {rel_path}")

        current = {
            platform: gather_item_info(items_by_platform[platform].get(rel_path), platform)
            for platform in PLATFORMS
        }
        # Kodi's resume query does not supply duration; use a real duration
        # from another platform for its bookmark total.
        known_duration = next(
            (current[p]["duration"] for p in PLATFORMS if current[p]["duration"] > 0), 0
        )
        if current["kodi"]["duration"] == 0:
            current["kodi"]["duration"] = known_duration

        present = [p for p in PLATFORMS if items_by_platform[p].get(rel_path)]
        if not present:
            # A temporary failed lookup must not erase an active baseline.
            if previous_entry:
                updated_sync_state[rel_path] = previous_entry
            continue
        updated_sync_state[rel_path] = {
            p: {
                "resume": current[p]["resume"],
                "duration": current[p]["duration"],
                "playcount": current[p]["playcount"],
                "status": current[p]["status"],
                ID_FIELDS[p]: current[p]["item_id"],
                "media_type": current[p]["media_type"],
            }
            for p in present
        }

        # Unstarted On Deck / Next Up entries are displayed and recorded, but
        # do not create a synthetic bookmark.
        if not present or not any(current[p]["resume"] or current[p]["playcount"] for p in present):
            if not previous_entry or not any(
                (previous_entry.get(p) or {}).get("resume", 0) for p in PLATFORMS
            ):
                continue

        previous = {p: gather_previous_info(previous_entry, p) for p in present}
        if previous_entry:
            changed = [
                p for p in present
                if p in previous_entry and (
                    current[p]["resume"] != previous[p]["resume"] or
                    current[p]["playcount"] != previous[p]["playcount"] or
                    current[p]["status"] != previous[p]["status"]
                )
            ]
            # A newly discovered copy is a destination, not a changed source.
            if not changed:
                active = [p for p in present if current[p]["resume"] > 0]
                if len(active) == 1 and any(
                    current[p]["resume"] != current[active[0]]["resume"]
                    for p in present if p != active[0]
                ):
                    changed = active
                else:
                    continue
        else:
            # There is no prior snapshot to order simultaneous changes.
            active = [p for p in present if current[p]["resume"] > 0]
            if not active or (
                len({current[p]["resume"] for p in active}) == 1
                and len(active) == len(present)
            ):
                continue
            changed = active

        values = {
            (current[p]["status"], current[p]["resume"] if current[p]["status"] == "in_progress" else 0)
            for p in changed
        }
        if len(values) != 1:
            console.print(f"[yellow]⚠️ Conflicting changes for {rel_path}; skipping until the source is clear.[/yellow]")
            # Retain baseline so this conflict can be rechecked on the next run.
            if previous_entry:
                updated_sync_state[rel_path] = previous_entry
            else:
                updated_sync_state.pop(rel_path, None)
            continue

        source = changed[0]
        status = current[source]["status"]
        resume = current[source]["resume"] if status == "in_progress" else 0
        if status == "in_progress" and not known_duration:
            console.print(f"[yellow]⚠️ Missing duration for {rel_path}; skipping resume update.[/yellow]")
            if previous_entry:
                updated_sync_state[rel_path] = previous_entry
            continue

        for platform in present:
            info = current[platform]
            if (
                info["status"] == status and
                (status != "in_progress" or info["resume"] == resume)
            ):
                continue
            sync_actions.append({
                "action": {
                    "in_progress": "update_resume",
                    "watched": "mark_watched",
                    "unwatched": "mark_unwatched",
                }[status],
                "platform": platform,
                "item_id": info["item_id"],
                "item": items_by_platform[platform][rel_path],
                "resume": resume,
                "duration": info["duration"] or known_duration,
                "status": status,
            })

    if show_fetched:
        for platform in PLATFORMS:
            items = fetched_items_report[platform]
            if items:
                console.print(f"\n[bold magenta]{platform.capitalize()} items fetched:[/bold magenta]")
                for rel_path in sorted(items):
                    item = items[rel_path]
                    console.print(f"  [dim]{rel_path}[/dim]:")
                    title = item.get("combined_title") or item.get("title") or "No title"
                    console.print(f"    [italic]{title}[/italic]")

    return sync_actions, updated_sync_state
