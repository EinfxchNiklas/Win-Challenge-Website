from dotenv import load_dotenv

# Muss vor allen anderen app-Modulen laufen, damit os.getenv() beim Import bereits die .env sieht
load_dotenv()
