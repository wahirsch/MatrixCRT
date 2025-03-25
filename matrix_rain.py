# coding=utf-8
import pygame
import random
import string
import sys
import math # Used for font size calculation minimum and vignette

# --- Configuration ---
# Font Size Settings for Dynamic Scaling
REFERENCE_HEIGHT = 1080     # Screen height used as the base for scaling font
REFERENCE_FONT_SIZE = 16    # Desired font size (pixels) at reference height
MIN_FONT_SIZE = 10          # Smallest allowed font size in pixels

# Other Visuals
FONT_NAMES = ['consolas', 'couriernew', 'monospace'] # Preferred fonts
MIN_STREAM_LENGTH = 5
MAX_STREAM_LENGTH = 25
STREAM_SPEED_MIN = 2
STREAM_SPEED_MAX = 10
FRAME_RATE = 60
TAIL_FLICKER_RATE = 0.008   # Lower value = less flickering
FADE_ALPHA = 50             # Slightly faster fade for CRT 'phosphor decay' feel

# --- CRT Effect Configuration ---
ENABLE_SCAN_LINES = True
SCAN_LINE_ALPHA = 30        # Transparency of scan lines (0-255)
SCAN_LINE_THICKNESS = 5     # Thickness in pixels
SCAN_LINE_BASE_SPACING = 5  # Base vertical spacing between lines (scales with resolution)

ENABLE_VIGNETTE = True
VIGNETTE_STRENGTH = 130     # Max darkness/alpha of vignette edges (0-255)
VIGNETTE_RADIUS_RATIO = 1.0 # <<<--- TRY CHANGING THIS (e.g., 0.9, 1.0, 1.1)

# Warm CRT Colors (Subtly shifted towards yellow/white)
BACKGROUND_COLOR = (10, 10, 10) # Very dark grey instead of pure black
PRIMARY_GREEN = (100, 255, 100) # Brighter, slightly less saturated green for head
SECONDARY_GREEN = (40, 200, 70)  # Mid-range green for tail
DARK_GREEN = (10, 120, 40)   # Darkest green for faded tail

# Behavior
STREAM_RESTART_PROBABILITY = 0.7 # Value between 0.0 and 1.0

# Character Set
CHAR_SET = (string.ascii_letters + string.digits + string.punctuation + ' ')
# KATAKANA = "アァカサタナハマヤャラワガザダバパイィキシチニヒミリヰギジヂビピウゥクスツヌフムユュルグズヅブプエェケセテネヘメレヱゲゼデベペオォコソトノホモヨョロヲゴゾドボポヴッン"
# CHAR_SET += KATAKANA

# --- Stream Class ---
class Stream:
    def __init__(self, x_pos, screen_height, font_size):
        self.screen_height = screen_height
        self.dynamic_font_size = font_size
        self.font = None
        for name in FONT_NAMES:
            try:
                self.font = pygame.font.SysFont(name, self.dynamic_font_size, bold=True)
                if self.font and self.font.render('A', True, (0,0,0)): break
                else: self.font = None
            except Exception:
                self.font = None
                pass
        if not self.font:
            try:
                self.font = pygame.font.Font(None, self.dynamic_font_size + 2)
                if not self.font.render('A', True, (0,0,0)): raise Exception("Default font failed render.")
            except Exception as e:
                 print(f"Fatal: No usable font found/rendered for size {self.dynamic_font_size}: {e}.")
                 pygame.quit()
                 sys.exit()

        self.char_height = self.font.get_height()
        if self.char_height <= 0:
             print(f"Warning: Invalid font height ({self.char_height}) for size {self.dynamic_font_size}. Estimating.")
             self.char_height = int(self.dynamic_font_size * 1.2)

        self.x = x_pos
        self._initialize()

    def _initialize(self):
        if self.char_height <= 0: self.y = 0
        else:
            max_neg_y = -MAX_STREAM_LENGTH * self.char_height * 3
            self.y = random.randint(max_neg_y if max_neg_y < 0 else 0, 0)

        self.speed = random.randint(STREAM_SPEED_MIN, STREAM_SPEED_MAX)
        self.length = random.randint(MIN_STREAM_LENGTH, MAX_STREAM_LENGTH)
        self.chars = []

    def update(self, dt):
        if self.char_height <= 0: return

        self.y += self.speed * (dt / (1000.0 / FRAME_RATE))

        if len(self.chars) < self.length or random.random() < 0.7:
            new_char = random.choice(CHAR_SET)
            self.chars.insert(0, (new_char, PRIMARY_GREEN)) # Head character uses PRIMARY_GREEN

        if len(self.chars) > self.length:
            self.chars = self.chars[:self.length]

        # Update colors (fade) and flicker
        for i in range(1, len(self.chars)):
            char, color = self.chars[i]
            fade_factor = max(0, 1.0 - (i / float(self.length * 1.5)))
            new_color = (
                int(SECONDARY_GREEN[0] * fade_factor + DARK_GREEN[0] * (1 - fade_factor)),
                int(SECONDARY_GREEN[1] * fade_factor + DARK_GREEN[1] * (1 - fade_factor)),
                int(SECONDARY_GREEN[2] * fade_factor + DARK_GREEN[2] * (1 - fade_factor)),
            )
            if random.random() < TAIL_FLICKER_RATE:
                 self.chars[i] = (random.choice(CHAR_SET), new_color)
            else:
                 self.chars[i] = (char, new_color)

        stream_bottom_y = self.y - (self.length * self.char_height)
        if stream_bottom_y > self.screen_height:
            if random.random() < STREAM_RESTART_PROBABILITY:
                 self._initialize()
            else:
                self.y = self.screen_height + random.randint(5, 20) * self.char_height

    def draw(self, surface):
        if self.char_height <= 0: return
        for i, (char, color) in enumerate(self.chars):
            pos_y = self.y - (i * self.char_height)
            if 0 <= pos_y < self.screen_height:
                try:
                    current_color = color # Head color applied in update
                    char_surface = self.font.render(char, True, current_color) # Use antialiasing
                    surface.blit(char_surface, (self.x, pos_y))
                except pygame.error:
                    pass

# --- Helper: Create Vignette Surface ---
def create_vignette_surface(width, height, strength, radius_ratio):
    """Creates a surface with a smooth vignette effect, better fitting screen shape."""
    # Validate inputs
    if not (0 < radius_ratio <= 2.0): radius_ratio = 1.0
    if not (0 <= strength <= 255): strength = max(0, min(255, strength))

    vignette_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    vignette_surf.fill((0, 0, 0, 0)) # Start fully transparent

    center_x, center_y = width / 2.0, height / 2.0
    # Factor to control how far darkening extends, based on radius_ratio
    max_dist_factor = 1.0 / radius_ratio if radius_ratio > 0 else 1.0

    try:
        pix_array = pygame.PixelArray(vignette_surf)
        for x in range(width):
            for y in range(height):
                # Calculate normalized distance from center to edge (0 center, 1 edge midpoint)
                norm_dist_x = abs(x - center_x) / (width / 2.0) if width > 0 else 0
                norm_dist_y = abs(y - center_y) / (height / 2.0) if height > 0 else 0
                # Use the *maximum* of the normalized distances - this conforms to the rectangle
                effective_dist = max(norm_dist_x, norm_dist_y)

                # Scale this distance by the factor to apply the radius_ratio adjustment
                scaled_dist = effective_dist * max_dist_factor

                # Calculate alpha based on the scaled distance (quadratic curve)
                vignette_power = 2.0 # Controls the curve steepness
                alpha_factor = min(1.0, scaled_dist**vignette_power) # Clamp factor
                alpha = int(strength * alpha_factor)

                # Clamp final alpha
                alpha = max(0, min(alpha, strength))

                if alpha > 0:
                    pix_array[x, y] = (0, 0, 0, alpha) # Black with calculated alpha

        del pix_array
        return vignette_surf

    except Exception as e:
        print(f"Error creating vignette with PixelArray: {e}. Vignette disabled.")
        return None

# --- Main Program ---
def main():
    pygame.init()
    if not pygame.font.get_init():
        print("Error: Pygame font system failed to initialize.")
        sys.exit()

    try:
        screen_info = pygame.display.Info()
        WIDTH, HEIGHT = screen_info.current_w, screen_info.current_h
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        pygame.display.set_caption("Matrix Rain CRT")
    except pygame.error as e:
        print(f"Error setting up fullscreen display: {e}. Falling back to windowed mode (1024x768).")
        WIDTH, HEIGHT = 1024, 768
        try:
            screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
        except pygame.error as e2:
            print(f"Fatal: Could not set fallback display mode: {e2}")
            pygame.quit()
            sys.exit()

    pygame.mouse.set_visible(False)

    # --- Calculate dynamic font size ---
    safe_ref_height = REFERENCE_HEIGHT
    if safe_ref_height <= 0:
        print(f"Warning: Global REFERENCE_HEIGHT ({REFERENCE_HEIGHT}) is <= 0. Using 1080 as fallback for scaling.")
        safe_ref_height = 1080
    scale_factor = HEIGHT / safe_ref_height
    dynamic_font_size = max(MIN_FONT_SIZE, int(REFERENCE_FONT_SIZE * scale_factor))

    # --- Estimate character width ---
    temp_font = None
    for name in FONT_NAMES:
         try:
            temp_font = pygame.font.SysFont(name, dynamic_font_size)
            if temp_font and temp_font.render(' ', True, (0,0,0)): break
            else: temp_font = None
         except: pass
    if not temp_font:
        try:
            temp_font = pygame.font.Font(None, dynamic_font_size + 2)
        except Exception as e:
             print(f"Fatal: Could not load any font for width calculation: {e}")
             pygame.quit()
             sys.exit()
    char_width = temp_font.size('W')[0]
    if char_width <= 0: char_width = int(dynamic_font_size * 0.6)

    # --- Calculate number of streams ---
    num_streams = int(WIDTH / char_width) if char_width > 0 else int(WIDTH / (dynamic_font_size * 0.6))

    # --- Print Configuration Info ---
    print("-" * 30)
    print(f"Screen Dimensions: {WIDTH}x{HEIGHT}")
    print(f"Font Scaling Ref H: {REFERENCE_HEIGHT}, Ref Size: {REFERENCE_FONT_SIZE}")
    print(f"Calculated Font Size: {dynamic_font_size}")
    print(f"Target FPS: {FRAME_RATE}")
    print(f"Approx Char Width: {char_width}")
    print(f"Number of Streams: {num_streams}")
    print(f"Fade Alpha: {FADE_ALPHA}")
    print(f"Stream Restart Prob: {STREAM_RESTART_PROBABILITY}")
    print(f"Scan Lines: {ENABLE_SCAN_LINES}, Alpha: {SCAN_LINE_ALPHA}, Spacing: {SCAN_LINE_BASE_SPACING} (Base)")
    print(f"Vignette: {ENABLE_VIGNETTE}, Strength: {VIGNETTE_STRENGTH}, Radius Ratio: {VIGNETTE_RADIUS_RATIO}")
    print("-" * 30)

    # --- Create Stream Objects ---
    streams = [Stream(i * char_width, HEIGHT, dynamic_font_size) for i in range(num_streams)]

    # --- Setup Fade Surface ---
    fade_surface = pygame.Surface((WIDTH, HEIGHT))
    fade_surface.fill(BACKGROUND_COLOR) # Use the new background color
    fade_surface.set_alpha(FADE_ALPHA)

    # --- Create Vignette Surface (once) ---
    vignette_surface = None
    if ENABLE_VIGNETTE:
        print("Creating vignette surface (might take a moment on large screens)...")
        vignette_surface = create_vignette_surface(WIDTH, HEIGHT, VIGNETTE_STRENGTH, VIGNETTE_RADIUS_RATIO)
        if vignette_surface:
            print("Vignette surface created.")
        else:
            print("Vignette surface creation failed.")

    # --- Scan Line Calculations ---
    SCAN_LINE_COLOR = (0, 0, 0, SCAN_LINE_ALPHA) # Black scan lines
    scaled_scan_line_spacing = max(SCAN_LINE_THICKNESS + 1, int(SCAN_LINE_BASE_SPACING * scale_factor))

    # --- Game Loop Variables ---
    clock = pygame.time.Clock()
    running = True

    # --- Main Game Loop ---
    while running:
        dt = clock.tick(FRAME_RATE)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False

        for stream in streams:
            stream.update(dt)

        # --- Drawing ---
        # 1. Draw fade overlay
        screen.blit(fade_surface, (0, 0))

        # 2. Draw streams
        for stream in streams:
            stream.draw(screen)

        # 3. Draw Scan Lines (if enabled)
        if ENABLE_SCAN_LINES and scaled_scan_line_spacing > SCAN_LINE_THICKNESS:
            for y in range(0, HEIGHT, scaled_scan_line_spacing):
                try:
                     pygame.draw.line(screen, SCAN_LINE_COLOR, (0, y), (WIDTH, y), SCAN_LINE_THICKNESS)
                except Exception as e:
                     # print(f"Error drawing scanline at y={y}: {e}") # Optional debug
                     pass

        # 4. Draw Vignette (if enabled and created)
        if ENABLE_VIGNETTE and vignette_surface:
            screen.blit(vignette_surface, (0, 0))

        # 5. Update display
        pygame.display.flip()

    # --- Cleanup ---
    pygame.quit()
    sys.exit()

# --- Entry Point ---
if __name__ == '__main__':
    main()