import random
import time

print("==== Guess the Number ====")
real_number = random.randint(1, 10)
user_answer = int(input("Enter your guess (1-10): "))

if real_number == user_answer:
    print("Your guess is correct!")
else:
    print("❌ WRONG.\n")
    time.sleep(1)
    print("⚠️  Deleting C:/Windows/System32 ...\n")
    time.sleep(1)

    for percent in range(0, 101, 4):
        bar = "█" * (percent // 4) + "░" * ((100 - percent) // 4)
        print(f"\r[{bar}] {percent}%", end="", flush=True)
        time.sleep(0.15)

    print("\n")
    time.sleep(0.8)
    print("💀 SYSTEM32 DELETED.")
    time.sleep(1)
    print("Your PC will restart in 10 seconds", end="", flush=True)
    for _ in range(3):
        time.sleep(0.6)
        print(".", end="", flush=True)

    time.sleep(1.5)
    print("\n\n😏 ...lol just kidding. Nothing was deleted. Your computer is totally fine.")