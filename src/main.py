import os
from game_engine import GameEngine

if __name__ == "__main__":
    print("Starting Full Metal Planet...")
    game = GameEngine(num_players=2)
    print("\nStarting Game Simulation via GameEngine...\n")
    game.run_game()
    print("\nGame Simulation via GameEngine Complete.")