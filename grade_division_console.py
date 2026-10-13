import mysql.connector
import getpass
import config

conn = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = config.DB_PASSWORD,
    database = "grade_db"
)
cursor = conn.cursor()
#program start
print("=" * 50)
print("WELCOME")
print()
who = input("Are you here as Administor ? (y/n):")
if who == "y":
    username = input("Please enter your name: ")
    while True:
        password = getpass.getpass("Password: ")
        if password == config.ADMIN_PASSWORD:
            break
        print("Wrong password")
    print(f"Hello! {username}")
    while True:
        print("1. Edit database")
        print("2. Grade calculate")
        print("3. Quit")
        req = input("Please select a menu:")
        if req == "1":
            while True:
                print("1. Register New student")
                print("2. Add grade")
                print("3. Back")
                data = input("What would you like to do ?: ")
                if data == "1":
                    while True:
                        id_no = input("Enter student ID (blank to quit): ")
                        if id_no == "":
                            break
                        name = input("Enter Name: ")
                        cls = input("Enter class: ")

                        cursor.execute(
                            "INSERT INTO students (id, name, class) VALUES (%s, %s, %s)",
                            (id_no, name, cls)
                        )
                        conn.commit()
                        while True:
                            get = input("Would you also like to add grade ? (y/n): ")
                            if get == "y" or get == "n":
                                break
                            print("Error! Please enter y or n")
                        if get == "y":
                            while True:
                                id_no = input("Enter student ID (blank to quit): ")
                                if id_no == "":
                                    break
                                subject = input("Enter subject: ")
                                while True:
                                    try:
                                        score = int(input("Enter subject score: "))
                                        break
                                    except ValueError:
                                        print("Please enter a real number")
                                cursor.execute(
                                    "INSERT INTO grade (id, subject, score) VALUES (%s, %s, %s)",
                                    (id_no, subject, score)
                                )
                                conn.commit()
                                while True:
                                    ans = input("Would you like to add another grade? (y/n): ")
                                    if ans == "y" or ans == "n":
                                        break
                                    print("Error! Please enter y or n")
                                if ans == "n":
                                    break
                        while True:
                            ask = input("Would you like to register another student ? (y/n): ")
                            if ask == "y" or ask == "n":
                                break
                            print("Error! Please enter y or n")
                        if ask == "n":
                            break
                elif data == "2":
                        while True:
                            id_no = input("Enter student ID (blank to quit): ")
                            if id_no == "":
                                break
                            subject = input("Enter subject: ")
                            while True:
                                try:
                                    score = int(input("Enter subject score: "))
                                    break
                                except ValueError:
                                    print("Please enter real number")

                            cursor.execute(
                                "INSERT INTO grade (id, subject, score) VALUES (%s, %s, %s)",
                                (id_no, subject, score)
                            )
                            conn.commit()
                            while True:
                                ans = input("Would yopu like to addd another grade? (y/n): ")
                                if ans == "y" or ans == "n":
                                    break
                                print("Error! Please enter y or n")
                            if ans == "n":
                                break
                elif data == "3":
                    break
                else:
                    print("Error! Please enter 1 , 2 or 3")
        elif req == "2":
            pass
        elif req == "3":
            break
        else:
            print("Error! Please enter 1, 2 or 3")  
                
cursor.close()
conn.close()

