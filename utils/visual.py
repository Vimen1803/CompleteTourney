from PIL import Image, ImageDraw, ImageFont
import io
import math

# Tamaño fijo 16:9
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

def generate_bracket_image(tourney, current_round, team_names, server_name="", server_icon_bytes=None, tourney_image_bytes=None):
    """
    Genera una imagen de bracket con ratio 16:9 que cubre todo el espacio.
    """
    
    BG_COLOR = (38, 35, 38)
    LINE_COLOR = (85, 80, 85)
    TEXT_COLOR = (220, 220, 220)
    SEED_COLOR = (180, 180, 180)
    FOOTER_BG = (30, 28, 30)
    WINNER_COLOR = (100, 200, 120)
    
    all_rounds = tourney.get('matches', [])
    if not all_rounds:
        return create_empty_bracket()
    
    tournament_winner_id = tourney.get('winner_id')
    
    img = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    fonts = load_fonts()
    
    FOOTER_HEIGHT = 40
    MARGIN_X = 15
    MARGIN_Y = 10
    
    bracket_area_width = CANVAS_WIDTH - (MARGIN_X * 2)
    bracket_area_height = CANVAS_HEIGHT - FOOTER_HEIGHT - MARGIN_Y
    bracket_start_y = MARGIN_Y
    
    num_rounds = len(all_rounds)
    first_round_matches = len(all_rounds[0])
    total_teams = first_round_matches * 2
    
    if total_teams >= 16:
        draw_double_bracket_fixed(draw, all_rounds, team_names, 
                                   MARGIN_X, bracket_start_y, 
                                   bracket_area_width, bracket_area_height,
                                   fonts, total_teams, current_round, tournament_winner_id)
    else:
        draw_single_bracket_fixed(draw, all_rounds, team_names,
                                   MARGIN_X, bracket_start_y,
                                   bracket_area_width, bracket_area_height,
                                   fonts, first_round_matches, current_round, tournament_winner_id)
    
    footer_y = CANVAS_HEIGHT - FOOTER_HEIGHT
    draw.rectangle([0, footer_y, CANVAS_WIDTH, CANVAS_HEIGHT], fill=FOOTER_BG)
    
    icon_bytes = tourney_image_bytes if tourney_image_bytes else server_icon_bytes
    text_x = 20
    
    if icon_bytes:
        try:
             with Image.open(io.BytesIO(icon_bytes)) as icon:
                 icon = icon.convert("RGBA")
                 icon = icon.resize((30, 30), Image.Resampling.LANCZOS)
                 img.paste(icon, (20, footer_y + 5), icon)
                 text_x = 60
        except:
             pass

    tourney_name = tourney.get('name', server_name or 'Torneo')
    draw.text((text_x, footer_y + 10), tourney_name, fill=TEXT_COLOR, font=fonts['footer'])
    
    if server_name:
        info_text = f"{server_name}"
        bbox = draw.textbbox((0, 0), info_text, font=fonts['footer_small'])
        text_width = bbox[2] - bbox[0]
        draw.text((CANVAS_WIDTH - text_width - 20, footer_y + 12), info_text, fill=SEED_COLOR, font=fonts['footer_small'])
    
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf


def draw_single_bracket_fixed(draw, all_rounds, team_names, start_x, start_y, 
                               area_width, area_height, fonts, first_round_matches, current_round, tournament_winner_id=None):
    """
    Dibuja un bracket simple que ocupa todo el espacio disponible
    """
    
    LINE_COLOR = (85, 80, 85)
    num_rounds = len(all_rounds)
    
    SLOT_WIDTH = min(180, (area_width - 40) // num_rounds)
    round_spacing = area_width // num_rounds
    
    match_height_available = area_height / first_round_matches
    slot_height = min(28, max(18, int(match_height_available * 0.35)))
    match_gap = min(15, max(5, int(match_height_available * 0.15)))
    
    match_block_height = slot_height * 2 + match_gap
    
    positions_cache = {}
    
    def get_match_y(round_idx, match_idx):
        """
        Obtiene la posición Y de un match
        """
        key = (round_idx, match_idx)
        if key in positions_cache:
            return positions_cache[key]
        
        if round_idx == 0:
            num_matches = first_round_matches
            total_space = area_height
            match_space = total_space / num_matches
            y = start_y + match_idx * match_space + (match_space - match_block_height) / 2
        else:
            prev_y1 = get_match_y(round_idx - 1, match_idx * 2)
            prev_y2 = get_match_y(round_idx - 1, match_idx * 2 + 1)
            center1 = prev_y1 + match_block_height / 2
            center2 = prev_y2 + match_block_height / 2
            y = (center1 + center2) / 2 - match_block_height / 2
        
        positions_cache[key] = y
        return y
    
    for round_idx, round_matches in enumerate(all_rounds):
        x_pos = start_x + round_idx * round_spacing
        is_past_round = (round_idx + 1) < current_round
        
        for match_idx, match in enumerate(round_matches):
            match_y = get_match_y(round_idx, match_idx)
            
            if round_idx == 0:
                seed1 = match_idx * 2 + 1
                seed2 = first_round_matches * 2 - match_idx * 2
            else:
                seed1 = ""
                seed2 = ""
            
            draw_match_slot(draw, match, team_names, x_pos, match_y,
                           SLOT_WIDTH, slot_height, match_gap, fonts, seed1, seed2,
                           is_past_round=is_past_round, tournament_winner_id=tournament_winner_id)
            
            line1_y = match_y + slot_height
            line2_y = match_y + slot_height * 2 + match_gap
            center_y = (line1_y + line2_y) / 2
            
            if round_idx < num_rounds - 1:
                connector_x = x_pos + SLOT_WIDTH
                gap_to_next = round_spacing - SLOT_WIDTH
                mid_x = connector_x + gap_to_next * 0.3
                next_x = start_x + (round_idx + 1) * round_spacing
                
                draw.line([(connector_x, line1_y), (mid_x, line1_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, line1_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(connector_x, line2_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, center_y), (next_x, center_y)], fill=LINE_COLOR, width=1)
            else:
                connector_x = x_pos + SLOT_WIDTH
                mid_x = connector_x + 15
                draw.line([(connector_x, line1_y), (mid_x, line1_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, line1_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(connector_x, line2_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, center_y), (mid_x + 25, center_y)], fill=LINE_COLOR, width=1)


def draw_double_bracket_fixed(draw, all_rounds, team_names, start_x, start_y,
                               area_width, area_height, fonts, total_teams, current_round, tournament_winner_id=None):
    """
    Dibuja un bracket doble corregido
    """
    
    LINE_COLOR = (85, 80, 85)
    num_rounds = len(all_rounds)
    first_round_matches = len(all_rounds[0])
    half_first_round = first_round_matches // 2
    rounds_per_side = 0
    temp_matches = half_first_round
    
    while temp_matches >= 1:
        rounds_per_side += 1
        temp_matches = temp_matches // 2
    
    center_space = 140
    side_width = (area_width - center_space) / 2
    
    SLOT_WIDTH = min(140, int(side_width / rounds_per_side * 0.7))
    round_spacing = side_width / rounds_per_side
    
    match_height_available = area_height / half_first_round
    slot_height = min(24, max(16, int(match_height_available * 0.35)))
    match_gap = min(12, max(4, int(match_height_available * 0.12)))
    match_block_height = slot_height * 2 + match_gap
    
    left_rounds = []
    right_rounds = []
    final_match = None
    
    for round_idx, round_matches in enumerate(all_rounds):
        n = len(round_matches)
        if n == 1:
            final_match = (round_matches[0], round_idx)
        elif n >= 2:
            half = n // 2
            left_rounds.append((round_matches[:half], round_idx))
            right_rounds.append((round_matches[half:], round_idx))
    
    left_positions = {}
    right_positions = {}
    
    def get_left_y(round_idx, match_idx):
        """
        Obtiene la posición Y de un match
        """
        key = (round_idx, match_idx)
        if key in left_positions:
            return left_positions[key]
        
        if round_idx == 0:
            num = half_first_round
            match_space = area_height / num
            y = start_y + match_idx * match_space + (match_space - match_block_height) / 2
        else:
            y1 = get_left_y(round_idx - 1, match_idx * 2)
            y2 = get_left_y(round_idx - 1, match_idx * 2 + 1)
            center1 = y1 + match_block_height / 2
            center2 = y2 + match_block_height / 2
            y = (center1 + center2) / 2 - match_block_height / 2
        
        left_positions[key] = y
        return y
    
    def get_right_y(round_idx, match_idx):
        """
        Obtiene la posición Y de un match
        """
        key = (round_idx, match_idx)
        if key in right_positions:
            return right_positions[key]
        
        if round_idx == 0:
            num = half_first_round
            match_space = area_height / num
            y = start_y + match_idx * match_space + (match_space - match_block_height) / 2
        else:
            y1 = get_right_y(round_idx - 1, match_idx * 2)
            y2 = get_right_y(round_idx - 1, match_idx * 2 + 1)
            center1 = y1 + match_block_height / 2
            center2 = y2 + match_block_height / 2
            y = (center1 + center2) / 2 - match_block_height / 2
        
        right_positions[key] = y
        return y
    
    center_x = CANVAS_WIDTH / 2
    
    for local_round_idx, (round_matches, actual_round_idx) in enumerate(left_rounds):
        x_pos = start_x + local_round_idx * round_spacing
        is_past_round = (actual_round_idx + 1) < current_round
        
        for match_idx, match in enumerate(round_matches):
            match_y = get_left_y(local_round_idx, match_idx)
            
            if local_round_idx == 0:
                seed1 = match_idx * 2 + 1
                seed2 = half_first_round * 2 - match_idx * 2
            else:
                seed1 = ""
                seed2 = ""
            
            draw_match_slot(draw, match, team_names, x_pos, match_y,
                           SLOT_WIDTH, slot_height, match_gap, fonts, seed1, seed2,
                           is_past_round=is_past_round, tournament_winner_id=tournament_winner_id)
            
            line1_y = match_y + slot_height
            line2_y = match_y + slot_height * 2 + match_gap
            center_y = (line1_y + line2_y) / 2
            connector_x = x_pos + SLOT_WIDTH
            
            if local_round_idx < len(left_rounds) - 1:
                gap = round_spacing - SLOT_WIDTH
                mid_x = connector_x + gap * 0.3
                next_x = start_x + (local_round_idx + 1) * round_spacing
                
                draw.line([(connector_x, line1_y), (mid_x, line1_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, line1_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(connector_x, line2_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, center_y), (next_x, center_y)], fill=LINE_COLOR, width=1)
            else:
                mid_x = connector_x + 15
                final_x = center_x - SLOT_WIDTH / 2
                draw.line([(connector_x, line1_y), (mid_x, line1_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, line1_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(connector_x, line2_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, center_y), (final_x, center_y)], fill=LINE_COLOR, width=1)
    
    for local_round_idx, (round_matches, actual_round_idx) in enumerate(right_rounds):
        x_pos = CANVAS_WIDTH - start_x - SLOT_WIDTH - local_round_idx * round_spacing
        is_past_round = (actual_round_idx + 1) < current_round
        
        for match_idx, match in enumerate(round_matches):
            match_y = get_right_y(local_round_idx, match_idx)
            
            if local_round_idx == 0:
                base = half_first_round * 2
                seed1 = base + match_idx * 2 + 1
                seed2 = total_teams - match_idx * 2
            else:
                seed1 = ""
                seed2 = ""
            
            draw_match_slot(draw, match, team_names, x_pos, match_y,
                           SLOT_WIDTH, slot_height, match_gap, fonts, seed1, seed2,
                           is_past_round=is_past_round, tournament_winner_id=tournament_winner_id)
            
            line1_y = match_y + slot_height
            line2_y = match_y + slot_height * 2 + match_gap
            center_y = (line1_y + line2_y) / 2
            connector_x = x_pos
            
            if local_round_idx < len(right_rounds) - 1:
                gap = round_spacing - SLOT_WIDTH
                mid_x = connector_x - gap * 0.3
                next_x = CANVAS_WIDTH - start_x - SLOT_WIDTH - (local_round_idx + 1) * round_spacing + SLOT_WIDTH
                
                draw.line([(connector_x, line1_y), (mid_x, line1_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, line1_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(connector_x, line2_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, center_y), (next_x, center_y)], fill=LINE_COLOR, width=1)
            else:
                mid_x = connector_x - 15
                final_x = center_x + SLOT_WIDTH / 2
                draw.line([(connector_x, line1_y), (mid_x, line1_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, line1_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(connector_x, line2_y), (mid_x, line2_y)], fill=LINE_COLOR, width=1)
                draw.line([(mid_x, center_y), (final_x, center_y)], fill=LINE_COLOR, width=1)
    
    if final_match:
        match, final_round_idx = final_match
        is_past_round = (final_round_idx + 1) < current_round
        
        final_x = center_x - SLOT_WIDTH / 2
        final_y = start_y + area_height / 2 - match_block_height / 2
        
        draw_match_slot(draw, match, team_names, final_x, final_y,
                       SLOT_WIDTH, slot_height, match_gap, fonts, "", "",
                       is_final=True, is_past_round=is_past_round, tournament_winner_id=tournament_winner_id)


def draw_match_slot(draw, match, team_names, x, y, slot_width, slot_height, match_gap, fonts, seed1, seed2, is_final=False, is_past_round=False, tournament_winner_id=None):
    """
    Dibuja un match individual. Muestra ganadores en verde si is_past_round=True, y al campeón en amarillo si tournament_winner_id está definido
    """
    
    TEXT_COLOR = (220, 220, 220)
    SEED_COLOR = (180, 180, 180)
    LINE_COLOR = (85, 80, 85)
    WINNER_COLOR = (100, 200, 120)
    FINAL_COLOR = (255, 215, 0)
    
    team1_id = match.get('team1_id')
    team2_id = match.get('team2_id')
    winner_id = match.get('winner_id')
    
    team1_name = "BYE" if team1_id == "BYE_SLOT" else team_names.get(team1_id, "BYE")
    team2_name = "BYE" if team2_id == "BYE_SLOT" else team_names.get(team2_id, "BYE")
    
    if not team1_id:
        team1_name = "BYE"
    if not team2_id:
        team2_name = "BYE"
    
    is_tournament_champion1 = tournament_winner_id and team1_id == tournament_winner_id
    is_tournament_champion2 = tournament_winner_id and team2_id == tournament_winner_id
    
    if is_past_round and winner_id:
        if (team1_id == "BYE_SLOT" or not team1_id) and (team2_id == "BYE_SLOT" or not team2_id):
            is_winner1 = True
            is_winner2 = False
        else:
            is_winner1 = winner_id == team1_id and team1_id is not None
            is_winner2 = winner_id == team2_id and team2_id is not None
    else:
        is_winner1 = False
        is_winner2 = False
    
    if is_tournament_champion1:
        text1_color = FINAL_COLOR
        seed1_color = FINAL_COLOR
    elif is_winner1:
        text1_color = WINNER_COLOR
        seed1_color = WINNER_COLOR
    else:
        text1_color = TEXT_COLOR
        seed1_color = SEED_COLOR
    
    if is_tournament_champion2:
        text2_color = FINAL_COLOR
        seed2_color = FINAL_COLOR
    elif is_winner2:
        text2_color = WINNER_COLOR
        seed2_color = WINNER_COLOR
    else:
        text2_color = TEXT_COLOR
        seed2_color = SEED_COLOR
    
    font_team = fonts['team']
    font_seed = fonts['seed']
    
    text_offset_y = max(2, (slot_height - 12) // 2)
    max_chars = max(12, int(slot_width / 7))
    
    team1_y = y
    if seed1:
        draw.text((x, team1_y + text_offset_y), str(seed1), fill=seed1_color, font=font_seed)
        name_x = x + 20
    else:
        name_x = x + 5
    
    display_name1 = team1_name[:max_chars] + ".." if len(team1_name) > max_chars else team1_name
    draw.text((name_x, team1_y + text_offset_y), display_name1, fill=text1_color, font=font_team)
    line1_y = team1_y + slot_height
    draw.line([(x, line1_y), (x + slot_width, line1_y)], fill=LINE_COLOR, width=1)
    
    team2_y = y + slot_height + match_gap
    if seed2:
        draw.text((x, team2_y + text_offset_y), str(seed2), fill=seed2_color, font=font_seed)
        name_x = x + 20
    else:
        name_x = x + 5
    
    display_name2 = team2_name[:max_chars] + ".." if len(team2_name) > max_chars else team2_name
    draw.text((name_x, team2_y + text_offset_y), display_name2, fill=text2_color, font=font_team)
    line2_y = team2_y + slot_height
    draw.line([(x, line2_y), (x + slot_width, line2_y)], fill=LINE_COLOR, width=1)


def load_fonts():
    """
    Carga las fuentes para el bracket
    """
    try:
        return {
            'title': ImageFont.truetype("arial.ttf", 18),
            'team': ImageFont.truetype("arial.ttf", 11),
            'seed': ImageFont.truetype("arial.ttf", 10),
            'footer': ImageFont.truetype("arialbd.ttf", 14),
            'footer_small': ImageFont.truetype("arial.ttf", 10)
        }
    except:
        try:
            return {
                'title': ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18),
                'team': ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11),
                'seed': ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10),
                'footer': ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14),
                'footer_small': ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            }
        except:
            default = ImageFont.load_default()
            return {'title': default, 'team': default, 'seed': default, 'footer': default, 'footer_small': default}


def create_empty_bracket():
    """
    Crea un bracket vacío 16:9
    """
    BG_COLOR = (38, 35, 38)
    TEXT_COLOR = (220, 220, 220)
    
    img = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()
    
    text = "No hay bracket disponible"
    bbox = draw.textbbox((0, 0), text, font=fonts['title'])
    text_width = bbox[2] - bbox[0]
    draw.text(((CANVAS_WIDTH - text_width) // 2, CANVAS_HEIGHT // 2 - 10), text, fill=TEXT_COLOR, font=fonts['title'])
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf