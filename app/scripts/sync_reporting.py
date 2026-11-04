from sync_shared import *

def add_platform_label_row(tbl):
    tbl.add_row(
        "",
        "[dim yellow]Plex[/dim yellow]",
        "[dim cyan]Kodi[/dim cyan]",
        "[dim blue]Jellyfin[/dim blue]",
        "",
    )


def is_up_next_episode(*items):
    present = [item for item in items if item]
    return (
        any(item.get("media_type") == "episode" and item.get("status") == "unwatched"
            for item in present)
        and all(int(item.get("resume") or 0) == 0 and item.get("status") != "watched"
                for item in present)
    )


def print_paths(plex_items, kodi_items, jellyfin_items):
    def split_by_type(items):
        movies = {k: v for k, v in items.items() if v.get("media_type") == "movie"}
        shows = {k: v for k, v in items.items() if v.get("media_type") in ("show", "episode")}
        return movies, shows

    plex_movies, plex_shows = split_by_type(plex_items)
    kodi_movies, kodi_shows = split_by_type(kodi_items)
    jelly_movies, jelly_shows = split_by_type(jellyfin_items)

    def make_on_deck_table(title, plex_items, kodi_items, jellyfin_items):
        table = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold green")
        table.add_column("Movie", style="green", no_wrap=False)
        table.add_column("Plex", justify="center", style="yellow", no_wrap=True)
        table.add_column("Kodi", justify="center", style="cyan", no_wrap=True)
        table.add_column("Jellyfin", justify="center", style="blue", no_wrap=True)
        table.add_column("Status", justify="center", style="magenta", no_wrap=True)

        all_paths = sorted(set(plex_items) | set(kodi_items) | set(jellyfin_items))

        for idx, path in enumerate(all_paths):
            p = plex_items.get(path)
            k = kodi_items.get(path)
            j = jellyfin_items.get(path)

            if not is_up_next_episode(p, k, j):
                continue

            movie_title = (p or k or j).get("combined_title") or (p or k or j).get("title") or "-"
            plex_resume = format_time(int(p.get("resume", 0))) if p else "-"
            kodi_resume = format_time(int(k.get("resume", 0))) if k else "-"
            jelly_resume = format_time(int(j.get("resume", 0))) if j else "-"
            status = "🌱"

            row = [
                movie_title,
                f"[yellow]{plex_resume}[/yellow]" if p else "-",
                f"[cyan]{kodi_resume}[/cyan]" if k else "-",
                f"[blue]{jelly_resume}[/blue]" if j else "-",
                f"[magenta]{status}[/magenta]"
            ]
            if idx % 2:
                row = [f"[dim]{cell}[/dim]" for cell in row]
            table.add_row(*row)

        return table

    def make_on_deck_table_shows(title, plex_items, kodi_items, jellyfin_items):
        table = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold green", show_header=False)
        table.add_column("Show", justify="left", style="bold green", no_wrap=False)
        table.add_column("Plex", justify="center", style="yellow", no_wrap=True)
        table.add_column("Kodi", justify="center", style="cyan", no_wrap=True)
        table.add_column("Jellyfin", justify="center", style="blue", no_wrap=True)
        table.add_column("Status", justify="center", style="magenta", no_wrap=True)

        add_platform_label_row(table)  # 👈 added

        all_paths = sorted(set(plex_items) | set(kodi_items) | set(jellyfin_items))

        for idx, path in enumerate(all_paths):
            p = plex_items.get(path)
            k = kodi_items.get(path)
            j = jellyfin_items.get(path)

            if not is_up_next_episode(p, k, j):
                continue

            show_title = (p or k or j).get("combined_title") or (p or k or j).get("title") or "-"
            plex_resume = format_time(int(p.get("resume", 0))) if p else "-"
            kodi_resume = format_time(int(k.get("resume", 0))) if k else "-"
            jelly_resume = format_time(int(j.get("resume", 0))) if j else "-"
            status = "🌱"

            row = [
                show_title,
                f"[yellow]{plex_resume}[/yellow]" if p else "-",
                f"[cyan]{kodi_resume}[/cyan]" if k else "-",
                f"[blue]{jelly_resume}[/blue]" if j else "-",
                f"[magenta]{status}[/magenta]"
            ]
            if idx % 2:
                row = [f"[dim]{cell}[/dim]" for cell in row]
            table.add_row(*row)

        return table

    def make_continue_watching_table_platform(platform_name, items, media_type, color):
        if platform_name == "Plex":
            status_label = "Continue Watching"
        elif platform_name == "Kodi":
            status_label = "In Progress"
        elif platform_name == "Jellyfin":
            status_label = "Continue Watching"
        else:
            status_label = "Watching"

        table = Table(
            box=box.SIMPLE_HEAD,
            title=f"▶ {platform_name.capitalize()} {status_label}",
            title_style=f"bold {color}",
            show_header=False,
            header_style="bold"
        )

        table.add_column("Title", style=f"bold {color}", no_wrap=False)
        table.add_column("Relative Path", style=color, no_wrap=False)
        table.add_column("Resume", style="cyan", no_wrap=False)
        table.add_column("Status", style="white", no_wrap=False)

        filtered_items = {
            k: v for k, v in items.items()
            if v.get("media_type") == media_type and v.get("status") != "unwatched" and v.get("resume", 0) > 0
        }

        for idx, path in enumerate(sorted(filtered_items)):
            item = filtered_items[path]
            title_str = item.get("combined_title") or item.get("title") or "-"
            rel_path = item.get("rel_path") or "-"
            resume_time = format_time(int(item.get("resume", 0)))
            status = "▶"

            row = [
                title_str,
                f"[{color}]{rel_path}[/{color}]",
                f"[{color}]{resume_time}[/{color}]",
                f"[{color}]{status}[/{color}]"
            ]
            if idx % 2:
                row = [f"[dim]{cell}[/dim]" for cell in row]
            table.add_row(*row)

        return table

    plex_continue_movies_table = make_continue_watching_table_platform("Plex", plex_movies, "movie", "yellow")
    kodi_continue_movies_table = make_continue_watching_table_platform("Kodi", kodi_movies, "movie", "cyan")
    jelly_continue_movies_table = make_continue_watching_table_platform("Jellyfin", jelly_movies, "movie", "blue")

    plex_continue_shows_table = make_continue_watching_table_platform("Plex", plex_shows, "show", "yellow")
    kodi_continue_shows_table = make_continue_watching_table_platform("Kodi", kodi_shows, "show", "cyan")
    jelly_continue_shows_table = make_continue_watching_table_platform("Jellyfin", jelly_shows, "show", "blue")

    on_deck_shows_table = make_on_deck_table_shows("🌱 On Deck | Next Up", plex_shows, kodi_shows, jelly_shows)

    console.rule("")
    console.print()

    if on_deck_shows_table.row_count > 0:
        console.print(on_deck_shows_table)
        console.print()

    for table in [
        plex_continue_movies_table,
        kodi_continue_movies_table,
        jelly_continue_movies_table,
        plex_continue_shows_table,
        kodi_continue_shows_table,
        jelly_continue_shows_table
    ]:
        if table.row_count > 0:
            console.print(table)
            console.print()


def print_sync_comparison(plex_items, kodi_items, jellyfin_items):
    console.print()

    def split_by_type(items):
        movies = {k: v for k, v in items.items() if v.get("media_type") == "movie"}
        shows = {k: v for k, v in items.items() if v.get("media_type") in ("show", "episode")}
        return movies, shows

    plex_movies, plex_shows = split_by_type(plex_items)
    kodi_movies, kodi_shows = split_by_type(kodi_items)
    jelly_movies, jelly_shows = split_by_type(jellyfin_items)

    def make_sync_table(title, items_plex, items_kodi, items_jelly, media_type):
        tbl = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold white", show_header=False)
        col_name = "Movie" if media_type == "movie" else "Show"
        tbl.add_column(col_name, style="white")
        tbl.add_column("Plex", justify="right", style="yellow")
        tbl.add_column("Kodi", justify="right", style="cyan")
        tbl.add_column("Jellyfin", justify="right", style="blue")
        tbl.add_column("Status", style="magenta", justify="center")

        add_platform_label_row(tbl)  # 👈 added

        all_paths = sorted(set(items_plex) | set(items_kodi) | set(items_jelly))

        for idx, path in enumerate(all_paths):
            pi = items_plex.get(path)
            ki = items_kodi.get(path)
            ji = items_jelly.get(path)

            base = pi or ki or ji or {}
            title_str = base.get("combined_title") or base.get("title") or "-"
            pres = int(pi.get("resume", 0)) if pi else 0
            kres = int(ki.get("resume", 0)) if ki else 0
            jres = int(ji.get("resume", 0)) if ji else 0

            plex_time = format_time(pres)
            kodi_time = format_time(kres)
            jelly_time = format_time(jres)

            if pres == kres == jres:
                action = "🌱" if is_up_next_episode(pi, ki, ji) else "✔"
            else:
                action = "🔄"

            row = [
                title_str,
                f"[yellow]{plex_time}[/yellow]" if pi else "-",
                f"[cyan]{kodi_time}[/cyan]" if ki else "-",
                f"[blue]{jelly_time}[/blue]" if ji else "-",
                action,
            ]

            if idx % 2:
                row = [f"[dim]{c}[/dim]" for c in row]

            tbl.add_row(*row)

        return tbl

    movie_table = make_sync_table("🔄 Sync Comparison", plex_movies, kodi_movies, jelly_movies, "movie")
    show_table = make_sync_table("", plex_shows, kodi_shows, jelly_shows, "show")

    if movie_table.row_count > 0:
        console.print(movie_table)
        console.print()
    if show_table.row_count > 0:
        console.print(show_table)


def print_sync_results(plex_items, kodi_items, jellyfin_items, actions):
    console.print()

    def split_by_type(items):
        movies = {k: v for k, v in items.items() if v.get("media_type") == "movie"}
        shows = {k: v for k, v in items.items() if v.get("media_type") in ("show", "episode")}
        return movies, shows

    plex_movies, plex_shows = split_by_type(plex_items)
    kodi_movies, kodi_shows = split_by_type(kodi_items)
    jelly_movies, jelly_shows = split_by_type(jellyfin_items)

    def make_sync_table(title, items_plex, items_kodi, items_jelly, media_type):
        tbl = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold white", show_header=False)
        col_name = "Movie" if media_type == "movie" else "Show"
        tbl.add_column(col_name, style="white")
        tbl.add_column("Plex", justify="right", style="yellow")
        tbl.add_column("Kodi", justify="right", style="cyan")
        tbl.add_column("Jellyfin", justify="right", style="blue")
        tbl.add_column("Status", style="magenta", justify="center")

        add_platform_label_row(tbl)  # 👈 added

        all_paths = sorted(set(items_plex) | set(items_kodi) | set(items_jelly))

        for idx, path in enumerate(all_paths):
            pi = items_plex.get(path)
            ki = items_kodi.get(path)
            ji = items_jelly.get(path)

            base = pi or ki or ji or {}
            title_str = base.get("combined_title") or base.get("title") or "-"
            pres = int(pi.get("resume", 0)) if pi else 0
            kres = int(ki.get("resume", 0)) if ki else 0
            jres = int(ji.get("resume", 0)) if ji else 0

            plex_time = format_time(pres)
            kodi_time = format_time(kres)
            jelly_time = format_time(jres)

            if pres == kres == jres:
                action = "🌱" if is_up_next_episode(pi, ki, ji) else "✅"
            else:
                action = "⚠"

            row = [
                title_str,
                f"[yellow]{plex_time}[/yellow]" if pi else "-",
                f"[cyan]{kodi_time}[/cyan]" if ki else "-",
                f"[blue]{jelly_time}[/blue]" if ji else "-",
                action,
            ]

            if idx % 2:
                row = [f"[dim]{c}[/dim]" for c in row]

            tbl.add_row(*row)

        return tbl

    movie_table = make_sync_table("✅ Sync Results", plex_movies, kodi_movies, jelly_movies, "movie")
    show_table = make_sync_table("", plex_shows, kodi_shows, jelly_shows, "show")

    if movie_table.row_count > 0:
        console.print(movie_table)
    if show_table.row_count > 0:
        console.print(show_table)

###################################################
############# PREVIOUS PRINT TABLE FUNCTIONS ###############
###################################################

# def print_paths_tables(plex_items, kodi_items, jellyfin_items):
    # #On Deck Table
    # on_deck_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[magenta]🌱 On Deck / Next Up Items",
        # title_style="bold magenta"
    # )
    # on_deck_table.add_column("Type", style="bold magenta", no_wrap=True)
    # on_deck_table.add_column("Item ID", style="magenta", no_wrap=True)
    # on_deck_table.add_column("Relative Path", style="white")
    # on_deck_table.add_column("Resume", style="magenta", justify="right")

   # # Collect unwatched items (only shown in On Deck)
    # for i, (rel_path, item) in enumerate(plex_items.items()):
        # if item.get("status") != "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("ratingKey") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[magenta]{media_type}[/magenta]",
            # f"[magenta]{item_id}[/magenta]",
            # f"[magenta]{rel_path}[/magenta]",
            # f"[magenta]{resume_str}[/magenta]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # on_deck_table.add_row(*row)

    # for i, (rel_path, item) in enumerate(kodi_items.items()):
        # if item.get("status") != "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("idFile") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[magenta]{media_type}[/magenta]",
            # f"[magenta]{item_id}[/magenta]",
            # f"[magenta]{rel_path}[/magenta]",
            # f"[magenta]{resume_str}[/magenta]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # on_deck_table.add_row(*row)

    # for i, (rel_path, item) in enumerate(jellyfin_items.items()):
        # if item.get("status") != "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("id") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[magenta]{media_type}[/magenta]",
            # f"[magenta]{item_id}[/magenta]",
            # f"[magenta]{rel_path}[/magenta]",
            # f"[magenta]{resume_str}[/magenta]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # on_deck_table.add_row(*row)

    # #Plex Table
    # plex_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[yellow]🎬 Plex Continue Watching Items",
        # title_style="white"
    # )
    # plex_table.add_column("Type", style="bold green", no_wrap=True)
    # plex_table.add_column("Item ID", style="yellow", no_wrap=True)
    # plex_table.add_column("Relative Path", style="white")
    # plex_table.add_column("Resume", style="yellow", justify="right")

    # for i, (rel_path, item) in enumerate(plex_items.items()):
        # if item.get("status") == "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # if resume <= 0:
            # continue
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("ratingKey") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[yellow]{media_type}[/yellow]",
            # f"[yellow]{item_id}[/yellow]",
            # f"[yellow]{rel_path}[/yellow]",
            # f"[yellow]{resume_str}[/yellow]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # plex_table.add_row(*row)

    # #Kodi Table
    # kodi_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[cyan]📺 Kodi In Progress Items",
        # title_style="white"
    # )
    # kodi_table.add_column("Type", style="cyan", no_wrap=True)
    # kodi_table.add_column("Item ID", style="cyan", no_wrap=True)
    # kodi_table.add_column("Relative Path", style="white")
    # kodi_table.add_column("Resume", style="cyan", justify="right")

    # for i, (rel_path, item) in enumerate(kodi_items.items()):
        # if item.get("status") == "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # if resume <= 0:
            # continue
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("idFile") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[cyan]{media_type}[/cyan]",
            # f"[cyan]{item_id}[/cyan]",
            # f"[cyan]{rel_path}[/cyan]",
            # f"[cyan]{resume_str}[/cyan]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # kodi_table.add_row(*row)

    # #Jellyfin Table
    # jelly_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[blue]🍇 Jellyfin Continue Watching Items",
        # title_style="blue"
    # )
    # jelly_table.add_column("Type", style="blue", no_wrap=True)
    # jelly_table.add_column("Item ID", style="blue", no_wrap=True)
    # jelly_table.add_column("Relative Path", style="white")
    # jelly_table.add_column("Resume", style="blue", justify="right")

    # for i, (rel_path, item) in enumerate(jellyfin_items.items()):
        # if item.get("status") == "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # if resume <= 0:
            # continue
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("id") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[blue]{media_type}[/blue]",
            # f"[blue]{item_id}[/blue]",
            # f"[blue]{rel_path}[/blue]",
            # f"[blue]{resume_str}[/blue]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # jelly_table.add_row(*row)

   # # Display Tables
    # console.rule("")
    # console.print("")

    # if on_deck_table.row_count > 0:
        # console.print(on_deck_table, style="magenta")
        # console.print("")

    # console.print(plex_table, style="yellow")
    # console.print(kodi_table, style="cyan")
    # console.print(jelly_table, style="blue")

# #Sync comparison results table
# def print_sync_comparison(plex_items, kodi_items, jellyfin_items):
    # console.print()
    # tbl = Table(box=box.SIMPLE_HEAD, title="[white]🔄 Pre-Sync Comparison", title_style="white")
    # tbl.add_column("[green]Type", style="green")
    # tbl.add_column("Title", style="white")
    # tbl.add_column("[yellow]Plex", justify="right", style="yellow")
    # tbl.add_column("[cyan]Kodi", justify="right", style="cyan")
    # tbl.add_column("[blue]Jellyfin", justify="right", style="blue")
    # tbl.add_column("[magenta]Action", style="magenta", justify="center")

    # #Filter only items with a resume >= 0
    # pd = {k: v for k, v in plex_items.items() if v.get("resume", 0) >= 0}
    # kd = {k: v for k, v in kodi_items.items() if v.get("resume", 0) >= 0}
    # jd = {k: v for k, v in jellyfin_items.items() if v.get("resume", 0) >= 0}

    # all_paths = sorted(set(pd) | set(kd) | set(jd))

    # for idx, rel_path in enumerate(all_paths):
        # pi = pd.get(rel_path)
        # ki = kd.get(rel_path)
        # ji = jd.get(rel_path)

       # # Use the first available title/metadata
        # base = pi or ki or ji or {}
        # title = base.get("combined_title") or base.get("title") or "-"
        # media_type = base.get("media_type", "Unknown").capitalize()

        # pres = int(pi.get("resume", 0)) if pi else 0
        # kres = int(ki.get("resume", 0)) if ki else 0
        # jres = int(ji.get("resume", 0)) if ji else 0

        # plex_time = format_time(pres) 
        # kodi_time = format_time(kres)        
        # jelly_time = format_time(jres)        
        
        # if pres == kres == jres:
            # action = "✔" if pres > 0 else "🌱"
        # else:
            # action = "🔄"

        # row = [media_type, title, plex_time, kodi_time, jelly_time, action]

      #  # Alternate row shading
        # if idx % 2:
            # row = [f"[dim]{c}[/dim]" for c in row]

        # tbl.add_row(*row)

    # console.print(tbl)
    
# #Final sync results table
# def print_final_sync_table(plex_items, kodi_items, jellyfin_items, actions):
    # console.print()
    # tbl = Table(box=box.SIMPLE_HEAD, title="[white]✅ Post-Sync State", title_style="white")
    # tbl.add_column("[green]Type", style="green")
    # tbl.add_column("Title", style="white")
    # tbl.add_column("[yellow]Plex", justify="right", style="yellow")
    # tbl.add_column("[cyan]Kodi", justify="right", style="cyan")
    # tbl.add_column("[blue]Jellyfin", justify="right", style="blue")
    # tbl.add_column("[magenta]Action", style="magenta", justify="center")

   # # Filter only items with a resume >= 0
    # pd = {k: v for k, v in plex_items.items() if v.get("resume", 0) >= 0}
    # kd = {k: v for k, v in kodi_items.items() if v.get("resume", 0) >= 0}
    # jd = {k: v for k, v in jellyfin_items.items() if v.get("resume", 0) >= 0}

    # all_paths = sorted(set(pd) | set(kd) | set(jd))

    # for idx, rel_path in enumerate(all_paths):
        # pi = pd.get(rel_path)
        # ki = kd.get(rel_path)
        # ji = jd.get(rel_path)

       # # Use the first available title/metadata
        # base = pi or ki or ji or {}
        # title = base.get("combined_title") or base.get("title") or "-"
        # media_type = base.get("media_type", "Unknown").capitalize()

        # pres = int(pi.get("resume", 0)) if pi else 0
        # kres = int(ki.get("resume", 0)) if ki else 0
        # jres = int(ji.get("resume", 0)) if ji else 0

        # plex_time = format_time(pres)
        # kodi_time = format_time(kres)
        # jelly_time = format_time(jres)

        # if pres == kres == jres:
            # action = "✅" if pres > 0 else "🌱"
        # else:
            # action = "⚠"

        # row = [media_type, title, plex_time, kodi_time, jelly_time, action]

     #  # Alternate row shading
        # if idx % 2:
            # row = [f"[dim]{c}[/dim]" for c in row]

        # tbl.add_row(*row)

    # console.print(tbl)
    
###################################################
################# MAIN FUNCTION ###################
###################################################

