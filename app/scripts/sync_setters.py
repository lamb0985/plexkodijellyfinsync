from sync_shared import *

def sync_items(sync_instructions, plex=None, kodi_db=None, jellyfin=None):
    if not sync_instructions:
        console.print(f"\n[bold green]No sync actions to perform at this time.", justify="center")
        return 0

    def plex_set_resume(item, resume, duration, status):
        try:
            title = item.get("title", "Unknown") if item else "Unknown"
            ratingKey = item.get("ratingKey") or "N/A"
            # time = format_time(int(resume))

            if ratingKey == "N/A":
                console.print(f"[red]❌ Plex: Missing ratingKey for '{title}'")
                return False

            plex_obj = plex.fetchItem(ratingKey)

            if status == "on_deck":
                console.print(f"[green]🌱 Plex: Marked {title} as on deck")
                return True

            elif status == "watched":
                plex_obj.markWatched()
                console.print(f"[yellow]👀 Plex: Marked '{title}' as watched")
                plex_obj.reload()
                return True

            elif status == "unwatched":
                plex_obj.markUnwatched()
                console.print(f"[yellow]🙈 Plex: Marked '{title}' as unwatched")
                plex_obj.reload()
                return True

            elif status == "in_progress":
                plex_obj.updateProgress(int(resume * 1000), state="stopped")
                console.print(f"[yellow]▶ Plex: Updated resume point for '{title}' to {resume}s")
                plex_obj.reload()
                return True

            else:
                console.print(f"[red]❌ Plex: Unknown status '{status}' for '{title}'")
                return False

        except Exception as e:
            traceback.print_exc()
            console.print(f"[red]❌ Plex: Failed to update '{title}' – {e}")
            return False

    def kodi_set_resume(item, resume, status, duration=0):
        try:
            title = item.get("title", "Unknown") if item else "Unknown"
            resume = int(round(resume))
            duration = int(round(duration))
            idFile = item.get("idFile") or "N/A"
            idMovie = item.get("idMovie")
            idEpisode = item.get("idEpisode")
            media_type = item.get("media_type")  # "movie" or "episode"

            if idFile == "N/A":
                console.print(f"[red]❌ Kodi: Missing idFile for '{title}'")
                return False

            with kodi_db.cursor(pymysql.cursors.DictCursor) as cursor:

                if status == "on_deck":
                    console.print(f"[cyan]🌱 Kodi:  Marked {title} as on deck")
                    return True

                elif status == "watched":
                    cursor.execute("DELETE FROM bookmark WHERE idFile = %s AND type = 1", (idFile,))
                    cursor.execute("UPDATE files SET playCount = 1, lastPlayed = NOW() WHERE idFile = %s", (idFile,))
                    console.print(f"[cyan]👀 Kodi: Marked '{title}' as watched")
                    kodi_db.commit()
                    return True

                elif status == "unwatched":
                    cursor.execute("DELETE FROM bookmark WHERE idFile = %s AND type = 1", (idFile,))
                    cursor.execute("UPDATE files SET playCount = NULL, lastPlayed = NULL WHERE idFile = %s", (idFile,))
                    console.print(f"[cyan]🙈 Kodi: Marked '{title}' as unwatched")
                    kodi_db.commit()
                    return True

                elif status == "in_progress":
                    cursor.execute("SELECT * FROM bookmark WHERE idFile = %s AND type = 1", (idFile,))
                    bookmark = cursor.fetchone()

                    console.print(f"[cyan]▶ Kodi: Updated resume point for '{title}' to {resume}s")

                    if bookmark:
                        cursor.execute(
                            "UPDATE bookmark SET timeInSeconds = %s, totalTimeInSeconds = %s WHERE idBookmark = %s",
                            (resume, duration, bookmark["idBookmark"])
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO bookmark (idFile, timeInSeconds, totalTimeInSeconds, type, player, playerState, thumbNailImage) "
                            "VALUES (%s, %s, %s, 1, '', '', '')",
                            (idFile, resume, duration)
                        )

                    kodi_db.commit()

                    # 🔁 Refresh Kodi library item
                    if media_type in ["movie", "episode"]:
                        kodi_rpc(
                            "VideoLibrary.RefreshMovie" if media_type == "movie" else "VideoLibrary.RefreshEpisode",
                            {"movieid": idMovie} if media_type == "movie" else {"episodeid": idEpisode}
                        )

                    return True

                else:
                    console.print(f"[red]❌ Kodi: Unknown status '{status}' for '{title}'")
                    return False

        except Exception as e:
            traceback.print_exc()
            console.print(f"[red]❌ Kodi: Failed to update '{item.get('title', 'Unknown')}' – {e}")
            return False

    def jellyfin_set_resume(item, resume, duration, status):
        try:
            title = item.get("title", "Unknown") if item else "Unknown"
            item_id = item.get("id") or "N/A"

            if item_id == "N/A":
                console.print(f"[red]❌ Jellyfin: Missing item ID for '{title}'")
                return False

            server = jellyfin.server
            token = jellyfin.token
            user_id = jellyfin.user_id
            headers = {"X-Emby-Token": token}

            # Fetch current user data
            get_url = f"{server}/Users/{user_id}/Items/{item_id}"
            get_response = requests.get(get_url, headers=headers, timeout=10)

            if get_response.status_code != 200:
                console.print(f"[red]❌ Jellyfin: Failed to fetch current user data for '{title}' – {get_response.status_code}")
                return False

            current_data = get_response.json().get("UserData", {})
            if not current_data:
                console.print(f"[red]❌ Jellyfin: No user data found for '{title}'")
                return False

            # Start with current user data as base payload
            payload = {
                "PlaybackPositionTicks": current_data.get("PlaybackPositionTicks", 0),
                "PlayCount": current_data.get("PlayCount", 0),
                "Played": current_data.get("Played", False),
                "IsFavorite": current_data.get("IsFavorite", False),
                "Likes": current_data.get("Likes"),
                "Rating": current_data.get("Rating"),
                "LastPlayedDate": current_data.get("LastPlayedDate")
            }

            if status == "on_deck":
                console.print(f"[blue]🌱 Jellyfin: Marked {title} as on deck")
                return True

            elif status == "watched":
                payload["PlaybackPositionTicks"] = 0
                payload["Played"] = True
                payload["PlayCount"] = max(1, payload.get("PlayCount", 0))
                console.print(f"[blue]👀 Jellyfin: Marked '{title}' as watched")

            elif status == "unwatched":
                payload["PlaybackPositionTicks"] = 0
                payload["Played"] = False
                payload["PlayCount"] = 0
                console.print(f"[blue]🙈 Jellyfin: Marked '{title}' as unwatched")

            elif status == "in_progress":
                payload["PlaybackPositionTicks"] = int(resume * 10_000_000)
                payload["Played"] = False
                payload["PlayCount"] = 0
                console.print(f"[blue]▶ Jellyfin: Updated resume point for '{title}' to {resume}s")

            else:
                console.print(f"[red]❌ Jellyfin: Unknown status '{status}' for '{title}'")
                return False

            post_url = f"{server}/UserItems/{item_id}/UserData?userId={user_id}"
            response = requests.post(post_url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                return True
            else:
                console.print(f"[red]❌ Jellyfin: Failed to update '{title}' – {response.status_code} {response.text}")
                return False

        except requests.RequestException as e:
            traceback.print_exc()
            console.print(f"[red]❌ Jellyfin: Exception updating '{title or item_id}' – {e}")
            return False


    success_count = 0
    
    for action in sync_instructions:
        platform = action["platform"]
        item = action.get("item")
        resume = action.get("resume", 0)
        duration = action.get("duration", 0)
        status = action["status"]

        with console.status(f"[magenta]Processing {platform.upper()} → {status}: {item.get('title', 'Unknown') if item else 'Unknown'}"):

            try:
                if platform == "plex" and plex and item:
                    if plex_set_resume(item, resume, duration, status):
                        success_count += 1
                elif platform == "kodi" and kodi_db and item:
                    if kodi_set_resume(item, resume, status, duration):
                        success_count += 1
                elif platform == "jellyfin" and jellyfin and item:
                    if jellyfin_set_resume(item, resume, duration, status):
                        success_count += 1
            except Exception as e:
                traceback.print_exc()
                console.print(f"[red]❌ Exception syncing '{platform}' – {e}")
                
    # console.print(f"[green]✅ Sync complete: {success_count} action(s) applied.")
    return success_count

###################################################
############# PRINT TABLE FUNCTIONS ###############
###################################################
