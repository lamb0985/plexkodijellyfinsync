from sync_shared import *

def fetch_items(
    platform,
    plex=None,
    plex_media_root=None,
    kodi_db=None,
    kodi_media_root=None,
    jellyfin=None,
    jellyfin_media_root=None,
    target_rel_path=None,
    media_type=None,
):
    def build_item_data(item, platform, media_root):
        abs_path = item["abs_path"]
        rel_path = normalize_path(abs_path, media_root)

        # Use your gather_item_info here to get item_id, resume, duration, playcount, status
        gathered = gather_item_info(item, platform, duration_fallback=0)

        title = item.get("title") or item.get("Name") or "-"
        combined = item.get("combined_title") or combined_title(item)

        return {
            "platform": platform,
            "item_id": gathered["item_id"],
            "rel_path": rel_path,
            "abs_path": abs_path,
            "duration": gathered["duration"],
            "resume": gathered["resume"],
            "playcount": gathered["playcount"],
            "status": gathered["status"],
            "title": title,
            "combined_title": combined,
            **item,
        }

    results = {}

    if platform == "plex":
        if not plex or not plex_media_root:
            return {}

        results = {}

        if target_rel_path:
            # Target path we want to match against Plex library
            for lib in plex.library.sections():
                if lib.title in PLEX_EXCLUDE_LIBRARIES:
                    continue
                if media_type and lib.type != media_type:
                    continue

                try:
                    # Handle TV shows
                    if lib.type == "show":
                        for show in lib.all():
                            for ep in show.episodes():
                                if not ep or not ep.media or not ep.media[0].parts:
                                    continue
                                abs_path = ep.media[0].parts[0].file
                                rel_path = normalize_path(abs_path, plex_media_root)
                                if rel_path == target_rel_path:
                                    built = {
                                        "ratingKey": ep.ratingKey,
                                        "title": ep.title or "-",
                                        "combined_title": combined_title(ep),
                                        "media_type": ep.type,
                                        "season": ep.seasonNumber,
                                        "episode": ep.index,
                                        "resume": int(ep.viewOffset or 0) // 1000,
                                        "duration": int(ep.duration or 0) // 1000,
                                        "playcount": ep.viewCount or 0,
                                        "abs_path": abs_path,
                                    }
                                    enriched = build_item_data(built, "plex", plex_media_root)
                                    results[enriched["rel_path"]] = enriched
                                    return results

                    # Handle Movies
                    elif lib.type == "movie":
                        for movie in lib.all():
                            if not movie or not movie.media or not movie.media[0].parts:
                                continue
                            abs_path = movie.media[0].parts[0].file
                            rel_path = normalize_path(abs_path, plex_media_root)
                            if rel_path == target_rel_path:
                                built = {
                                    "ratingKey": movie.ratingKey,
                                    "title": movie.title or "-",
                                    "combined_title": combined_title(movie),
                                    "media_type": movie.type,
                                    "resume": int(movie.viewOffset or 0) // 1000,
                                    "duration": int(movie.duration or 0) // 1000,
                                    "playcount": movie.viewCount or 0,
                                    "abs_path": abs_path,
                                }
                                enriched = build_item_data(built, "plex", plex_media_root)
                                results[enriched["rel_path"]] = enriched
                                return results
                                
                except Exception as e:
                    console.print(f"[yellow]⚠️ Plex scan failed in {lib.title}: {e}")

        else:
            # Fetch continue watching from On Deck
            for lib in plex.library.sections():
                if lib.title in PLEX_EXCLUDE_LIBRARIES:
                    continue
                try:
                    for item in lib.onDeck():
                        if not item.media or not item.media[0].parts:
                            continue
                        resume = int(item.viewOffset or 0) // 1000
                        abs_path = item.media[0].parts[0].file
                        built = {
                            "ratingKey": item.ratingKey,
                            "title": item.title or "-",
                            "duration": int(item.duration or 0) // 1000,
                            "resume": resume,
                            "playcount": item.viewCount or 0,
                            "combined_title": combined_title(item),
                            "media_type": item.type,
                            "abs_path": abs_path,
                        }
                        enriched = build_item_data(built, "plex", plex_media_root)
                        results[enriched["rel_path"]] = enriched

                except Exception as e:
                    console.print(f"[yellow]⚠️ Plex library {lib.title} skipped: {e}")

            return results

    elif platform == "kodi":
        if not kodi_db or not kodi_media_root:
            return {}

        with kodi_db.cursor() as cursor:
            if target_rel_path:
                search_abs_path = denormalize_path(target_rel_path, kodi_media_root)
                cursor.execute("""
                    SELECT f.idFile, f.strFilename, p.strPath
                    FROM files f
                    JOIN path p ON f.idPath = p.idPath
                    WHERE CONCAT(p.strPath, f.strFilename) = %s
                """, (search_abs_path,))
                file_row = cursor.fetchone()
                if file_row:
                    idFile = file_row["idFile"]
                    abs_path = os.path.join(file_row["strPath"], file_row["strFilename"]).replace("\\", "/")

                    # Try movie first
                    cursor.execute("""
                        SELECT
                            m.c00 AS title,
                            m.c11 AS duration,
                            f.playCount,
                            bm.timeInSeconds AS resume,
                            m.idMovie
                        FROM movie m
                        JOIN files f ON m.idFile = f.idFile
                        LEFT JOIN bookmark bm
                            ON bm.idFile = f.idFile
                           AND bm.type = 1
                        WHERE m.idFile = %s
                    """, (idFile,))
                    row = cursor.fetchone()
                    if row:
                        built = {
                            "idFile": idFile,
                            "idMovie": row["idMovie"],
                            "title": row["title"] or "-",
                            "duration": int(row["duration"] or 0),
                            "resume": int(round(row["resume"])) if row["resume"] else 0,
                            "playcount": row["playCount"] or 0,
                            "abs_path": abs_path,
                            "media_type": "movie",
                        }
                        enriched = build_item_data(built, "kodi", kodi_media_root)
                        results[enriched["rel_path"]] = enriched
                        return results

                    # Try episode if not a movie
                    cursor.execute("""
                        SELECT
                            e.c00 AS episode_title,
                            e.c12 AS season,
                            e.c13 AS episode,
                            s.c00 AS show_title,
                            f.playCount,
                            bm.timeInSeconds AS resume,
                            e.idEpisode
                        FROM episode e
                        JOIN tvshow s ON e.idShow = s.idShow
                        JOIN files f ON e.idFile = f.idFile
                        LEFT JOIN bookmark bm
                            ON bm.idFile = f.idFile
                           AND bm.type = 1
                        WHERE e.idFile = %s
                    """, (idFile,))
                    row = cursor.fetchone()
                    if row:
                        combined = f"{row['show_title']} S{int(row['season']):02}E{int(row['episode']):02} – {row['episode_title']}"
                        built = {
                            "idFile": idFile,
                            "idEpisode": row["idEpisode"],
                            "title": row["episode_title"] or "-",
                            "duration": 0,
                            "resume": int(round(row["resume"])) if row["resume"] else 0,
                            "playcount": row["playCount"] or 0,
                            "abs_path": abs_path,
                            "media_type": "episode",
                            "combined_title": combined,
                        }
                        enriched = build_item_data(built, "kodi", kodi_media_root)
                        results[enriched["rel_path"]] = enriched
                        return results

            else:
                # Movies with resume
                cursor.execute("""
                    SELECT m.idMovie, m.c00 AS title, f.idFile, m.c22 AS folderPath, f.strFilename,
                           bm.timeInSeconds AS resume, f.playCount
                    FROM movie m
                    JOIN files f ON m.idFile = f.idFile
                    JOIN bookmark bm ON bm.idFile = f.idFile AND bm.type = 1 AND bm.timeInSeconds > 0
                    WHERE m.c22 LIKE %s
                """, (f'%{kodi_media_root}%',))
                for row in cursor.fetchall():
                    resume = int(round(row["resume"])) if row["resume"] else 0
                    abs_path = os.path.join(row["folderPath"].rstrip("/"), row["strFilename"]).replace("\\", "/")
                    built = {
                        "idFile": row["idFile"],
                        "idMovie": row["idMovie"],
                        "title": row["title"] or "-",
                        "duration": 0,
                        "resume": resume,
                        "playcount": row["playCount"] or 0,
                        "abs_path": abs_path,
                        "media_type": "movie",
                    }
                    enriched = build_item_data(built, "kodi", kodi_media_root)
                    results[enriched["rel_path"]] = enriched

                # Episodes with resume
                cursor.execute("""
                    SELECT e.idEpisode, e.c00 AS title, f.idFile, s.c00 AS showTitle, e.c12 AS season,
                           e.c13 AS episode, f.strFilename, p.strPath, bm.timeInSeconds AS resume, f.playCount
                    FROM episode e
                    JOIN files f ON e.idFile = f.idFile
                    JOIN path p ON f.idPath = p.idPath
                    JOIN tvshow s ON e.idShow = s.idShow
                    JOIN bookmark bm ON bm.idFile = f.idFile AND bm.type = 1 AND bm.timeInSeconds > 0
                    WHERE p.strPath LIKE %s
                """, (f'%{kodi_media_root}%',))
                for row in cursor.fetchall():
                    resume = int(round(row["resume"])) if row["resume"] else 0
                    abs_path = os.path.join(row["strPath"].rstrip("/"), row["strFilename"]).replace("\\", "/")
                    combined = f"{row['showTitle']} S{int(row['season']):02}E{int(row['episode']):02} – {row['title']}"
                    built = {
                        "idFile": row["idFile"],
                        "idEpisode": row["idEpisode"],
                        "title": row["title"] or "-",
                        "duration": 0,
                        "resume": resume,
                        "playcount": row["playCount"] or 0,
                        "abs_path": abs_path,
                        "media_type": "episode",
                        "combined_title": combined,
                    }
                    enriched = build_item_data(built, "kodi", kodi_media_root)
                    results[enriched["rel_path"]] = enriched

                return results
        
    elif platform == "jellyfin":
        if not jellyfin or not jellyfin_media_root:
            return {}

        token = jellyfin.token
        user_id = jellyfin.user_id
        server = jellyfin.server
        headers = {"X-Emby-Token": token}
        results = {}

        try:
            if target_rel_path:
                # Handling specific target_rel_path search
                search_abs_path = denormalize_path(target_rel_path, jellyfin_media_root)
                url = f"{server}/Items"
                params = {
                    "UserId": user_id,
                    "Recursive": "true",
                    "IncludeItemTypes": "Movie,Episode",
                    "Fields": "Path,UserData,RunTimeTicks",
                }
                r = requests.get(url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                items = r.json().get("Items", [])

                for item in items:

                    # if int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000) <= 0:
                        # continue  # Skip if there's no valid resume data
                    
                    abs_path = item.get("Path")
                    if abs_path == search_abs_path:
                        # Directly access fields inside the built dictionary
                        built = {
                            "id": item.get("Id"),
                            "title": item.get("Name") or "-",
                            "duration": int(item.get("RunTimeTicks", 0) // 10_000_000),
                            "resume": int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000),
                            "playcount": item.get("UserData", {}).get("PlayCount", 0),
                            "abs_path": abs_path,
                            "media_type": item.get("Type", "").lower(),
                        }
                        enriched = build_item_data(built, "jellyfin", jellyfin_media_root)
                        results[enriched["rel_path"]] = enriched
                        return results  # Return immediately after finding the match

            else:

                # Handling resume items if no target_rel_path
                url = f"{server}/UserItems/Resume"
                params = {
                    "userId": user_id,
                    "enableUserData": "true",
                    "Limit": 1000,
                    "Fields": "Path,UserData,RunTimeTicks",
                }
                r = requests.get(url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                items = r.json().get("Items", [])

                for item in items:
                    built = {
                        "id": item.get("Id"),
                        "title": item.get("Name") or "-",
                        "duration": int(item.get("RunTimeTicks", 0) // 10_000_000),
                        "resume": int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000),
                        "playcount": item.get("UserData", {}).get("PlayCount", 0),
                        "abs_path": item.get("Path"),
                        "media_type": item.get("Type", "").lower(),
                    }
                    enriched = build_item_data(built, "jellyfin", jellyfin_media_root)
                    results[enriched["rel_path"]] = enriched
                    
                # Also fetch "Next Up" episodes
                url = f"{server}/Shows/NextUp"
                params = {
                    "userId": user_id,
                    "enableUserData": "true",
                    "Limit": 1000,
                    "Fields": "Path,UserData,RunTimeTicks",
                }
                r = requests.get(url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                items = r.json().get("Items", [])

                for item in items:
                    built = {
                        "id": item.get("Id"),
                        "title": item.get("Name") or "-",
                        "duration": int(item.get("RunTimeTicks", 0) // 10_000_000),
                        "resume": int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000),
                        "playcount": item.get("UserData", {}).get("PlayCount", 0),
                        "abs_path": item.get("Path"),
                        "media_type": item.get("Type", "").lower(),
                    }
                    enriched = build_item_data(built, "jellyfin", jellyfin_media_root)
                    results[enriched["rel_path"]] = enriched
                return results                 
        except Exception as e:
            console.print(f"[blue]⚠️ Jellyfin fallback search failed: {e}")



    else:
        return {}

##################################################
############# SYNC LOGIC FUNCTIONS ###############
##################################################
    
