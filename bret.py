import pygame
import random

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 800  # Increased height to accommodate the button below the grid
GRID_SIZE = 8
CARD_SIZE = 60
MARGIN = 5
TOP_MARGIN = 50
BOTTOM_MARGIN = 100

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)

# Set up the display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("BRET Task")

# Font
font = pygame.font.Font(None, 36)


class Card:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, CARD_SIZE, CARD_SIZE)
        self.selected = False
        self.is_bomb = False

    def draw(self, surface, reveal=False):
        if reveal and self.selected:
            color = RED if self.is_bomb else GREEN
            text = ":(" if self.is_bomb else ":)"
        else:
            color = YELLOW if self.selected else GRAY
            text = "?" if self.selected else ""

        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, BLACK, self.rect, 2)

        if text:
            text_surface = font.render(text, True, BLACK)
            text_rect = text_surface.get_rect(center=self.rect.center)
            surface.blit(text_surface, text_rect)


# Create cards
cards = [Card(MARGIN + (CARD_SIZE + MARGIN) * (i % GRID_SIZE),
              TOP_MARGIN + (CARD_SIZE + MARGIN) * (i // GRID_SIZE))
         for i in range(GRID_SIZE * GRID_SIZE)]

# Create button
button_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT - BOTTOM_MARGIN, 200, 50)

# Game state
game_phase = "selection"  # Can be "selection", "reveal", or "end"
score = 0
bomb_index = None

# Main game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()
            if game_phase == "selection":
                for card in cards:
                    if card.rect.collidepoint(pos):
                        card.selected = not card.selected
                        if card.selected:
                            score += 10
                        else:
                            score -= 10  # Decrease score if card is deselected
                        score = max(0, score)  # Ensure score doesn't go below 0

                if button_rect.collidepoint(pos):
                    game_phase = "reveal"
                    bomb_index = random.randint(0, len(cards) - 1)
                    cards[bomb_index].is_bomb = True
                    final_score = score if not cards[bomb_index].selected else 0
            elif game_phase == "end" and button_rect.collidepoint(pos):
                game_phase = "selection"
                score = 0
                bomb_index = None
                for card in cards:
                    card.selected = False
                    card.is_bomb = False

    # Clear the screen
    screen.fill(WHITE)

    # Draw cards
    for card in cards:
        card.draw(screen, reveal=(game_phase in ["reveal", "end"]))

    # Draw score and card count
    score_text = font.render(f"Your potential payout is: {score}", True, BLACK)
    screen.blit(score_text, (40, 10))

    selected_count = sum(card.selected for card in cards)
    remaining_count = 64 - selected_count
    count_text = font.render(f"Selected: {selected_count} | Remaining: {remaining_count}", True, BLACK)
    screen.blit(count_text, (WIDTH - 300, TOP_MARGIN))

    # Draw score
    if game_phase == "selection":
        score_text = font.render(f"Your potential payout is: {score}", True, BLACK)
    else:
        score_text = font.render(f"Final score: {final_score}", True, BLACK)
    screen.blit(score_text, (40, 10))

    # Draw button
    pygame.draw.rect(screen, GREEN if game_phase == "selection" else GRAY, button_rect)
    pygame.draw.rect(screen, BLACK, button_rect, 2)
    button_text = font.render("Turn Cards" if game_phase == "selection" else "Play Again", True, BLACK)
    button_text_rect = button_text.get_rect(center=button_rect.center)
    screen.blit(button_text, button_text_rect)

    # Draw result text
    if game_phase in ["reveal", "end"]:
        if game_phase == "reveal":
            game_phase = "end"
        if cards[bomb_index].selected:
            result_text = font.render("You hit the bomb! Game Over!", True, BLACK)
        else:
            result_text = font.render(f"You won {final_score} points!", True, BLACK)
        screen.blit(result_text, (WIDTH // 2 - result_text.get_width() // 2, HEIGHT - BOTTOM_MARGIN - 60))

    # Update the display
    pygame.display.flip()

# Quit the game
pygame.quit()