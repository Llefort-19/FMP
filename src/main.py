import os
import pygame
from .game_engine import GameEngine
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, GAME_TITLE

if __name__ == "__main__":
    print("Starting Full Metal Planet...")
    game = GameEngine(num_players=2)
    print("\nStarting Game Simulation via GameEngine...\n")
    game.run_game()
    print("\nGame Simulation via GameEngine Complete.")