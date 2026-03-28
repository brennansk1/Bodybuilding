"""
Food Database Expansion — Additional bodybuilding foods.
Imported and merged into the main food database at module load time.
"""
from app.engines.engine3.food_database import FoodItem

EXPANDED_PROTEINS = [
    FoodItem("Ground Bison (93/7)", "protein", 26.0, 0.0, 7.0, 170, 150, 100, 250,
             phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Mahi Mahi", "protein", 24.0, 0.0, 1.0, 109, 170, 100, 250,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan")),
    FoodItem("Scallops", "protein", 21.0, 3.0, 1.0, 111, 150, 80, 200,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegetarian", "vegan", "no_shellfish")),
    FoodItem("Whey Protein Isolate", "protein", 90.0, 2.0, 1.0, 370, 30, 25, 50,
             peri_workout=True, phase_tags=("all",), exclude_tags=("vegan", "dairy_free")),
    FoodItem("Casein Protein Powder", "protein", 80.0, 4.0, 2.0, 360, 35, 25, 50,
             phase_tags=("all",), exclude_tags=("vegan", "dairy_free")),
    FoodItem("Turkey Bacon", "protein", 20.0, 2.0, 14.0, 218, 40, 20, 80,
             phase_tags=("bulk", "maintain"), exclude_tags=("vegetarian", "vegan")),
]

EXPANDED_CARBS = [
    FoodItem("Cream of Wheat", "carb", 10.0, 73.0, 1.0, 360, 40, 25, 80,
             peri_workout=True, phase_tags=("all",), exclude_tags=()),
    FoodItem("Basmati Rice (cooked)", "carb", 3.0, 28.0, 0.3, 130, 200, 100, 400,
             peri_workout=True, phase_tags=("all",), exclude_tags=()),
    FoodItem("Whole Wheat Pasta (cooked)", "carb", 5.5, 27.0, 1.0, 131, 200, 100, 350,
             phase_tags=("bulk", "maintain"), exclude_tags=("gluten_free",)),
    FoodItem("White Pasta (cooked)", "carb", 5.0, 31.0, 0.9, 158, 200, 100, 350,
             peri_workout=True, phase_tags=("all",), exclude_tags=("gluten_free",)),
    FoodItem("Sourdough Bread", "carb", 8.0, 50.0, 3.0, 274, 50, 30, 100,
             phase_tags=("bulk", "maintain"), exclude_tags=("gluten_free",)),
    FoodItem("Plain Bagel", "carb", 10.0, 53.0, 1.5, 257, 100, 60, 120,
             peri_workout=True, phase_tags=("bulk", "maintain"), exclude_tags=("gluten_free",)),
    FoodItem("Corn Tortillas", "carb", 6.0, 44.0, 3.0, 218, 60, 30, 90,
             phase_tags=("all",), exclude_tags=("gluten_free",)),
    FoodItem("Dates (Medjool)", "carb", 2.5, 75.0, 0.4, 277, 40, 20, 80,
             peri_workout=True, phase_tags=("all",), exclude_tags=()),
]

EXPANDED_FATS = [
    FoodItem("MCT Oil", "fat", 0.0, 0.0, 100.0, 862, 14, 5, 25,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Macadamia Nuts", "fat", 8.0, 14.0, 76.0, 718, 28, 14, 40,
             phase_tags=("bulk", "maintain"), exclude_tags=()),
    FoodItem("Cashews", "fat", 18.0, 30.0, 44.0, 553, 28, 14, 50,
             phase_tags=("bulk", "maintain"), exclude_tags=()),
    FoodItem("Egg Yolks", "fat", 16.0, 1.0, 27.0, 322, 50, 30, 80,
             phase_tags=("bulk", "maintain"), exclude_tags=("vegan",)),
]

EXPANDED_FRUITS = [
    FoodItem("Mango", "fruit", 0.8, 15.0, 0.4, 60, 150, 80, 200,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Grapes", "fruit", 0.7, 18.0, 0.2, 69, 120, 60, 200,
             phase_tags=("all",), exclude_tags=()),
    FoodItem("Watermelon", "fruit", 0.6, 8.0, 0.2, 30, 200, 100, 300,
             peri_workout=True, phase_tags=("all",), exclude_tags=()),
    FoodItem("Dates (whole)", "fruit", 2.5, 75.0, 0.4, 277, 30, 15, 60,
             peri_workout=True, phase_tags=("all",), exclude_tags=()),
]

ALL_EXPANDED_FOODS = EXPANDED_PROTEINS + EXPANDED_CARBS + EXPANDED_FATS + EXPANDED_FRUITS
