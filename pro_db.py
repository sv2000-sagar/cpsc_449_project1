import sqlite3
import datetime

def create_database():
    conn = sqlite3.connect("pro1.db")  
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Instructors (
            InstructorId INTEGER PRIMARY KEY,
            FirstName TEXT,
            LastName TEXT,
            Email TEXT
        )
    ''')
    conn.executescript('''
                        insert into Instructors(FirstName,LastName,Email) values('Dr.Jane','Doe','abc@gmail.com');
                        insert into Instructors(FirstName,LastName,Email) values('Dr.John','Doe','johndoe@gmail.com');
                       ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Classes (
            ClassId INTEGER PRIMARY KEY,
            InstructorId INT REFERENCES Instructors(InstructorId),
            Department TEXT,
            CourseCode TEXT,
            SectionNumber INTEGER,
            ClassName TEXT,
            CurrentEnrollment INTEGER,
            MaxEnrollment INTEGER,
            AutomaticEnrollmentFrozen INTEGER DEFAULT 0
        )
    ''')
    conn.executescript('''
                    insert into Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,\
                 CurrentEnrollment,MaxEnrollment) values('Computer Science','CPSC449',1,\
                 'Web-backend Engineering',1,34,40);
                    insert into Classes(Department,CourseCode,SectionNumber,ClassName,InstructorID,\
                 CurrentEnrollment,MaxEnrollment) values('Computer Science','CPSC332',1,\
                 'Compilers Design',2,40,40);
                 ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Students (
            StudentId INTEGER PRIMARY KEY,
            FirstName TEXT,
            LastName TEXT,
            Email TEXT
        )
    ''')
    conn.executescript('''
                    insert into Students(FirstName,LastName,Email) values('John','Doe','xyz@csuf.fullerton.edu');
                    insert into Students(FirstName,LastName,Email) values('Jane','Doe','abc@csuf.fullerton.edu');
                     ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Enrollments (
            EnrollmentId INTEGER PRIMARY KEY,
            StudentId INT REFERENCES Students(StudentId),
            ClassId INT REFERENCES Classes(ClassId),
            EnrollmentDate TEXT,
            Dropped INT DEFAULT 0
        )
    ''')
    
    conn.execute("insert into Enrollments(StudentID,ClassID,EnrollmentDate) values(1,1,datetime('now'));",)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS WaitingLists (
            WaitListId INTEGER PRIMARY KEY,
            StudentId INT REFERENCES Students(StudentId),
            ClassId INT REFERENCES Classes(ClassId),
            WaitingListPos INT,
            DateAdded TEXT
        )
    ''')
    
    conn.execute("insert into waitingLists(StudentID,ClassID,WaitingListPos,DateAdded) values(1,1,1,datetime('now'));",)

    

    conn.commit()
    conn.close()

create_database()