import collections
import contextlib
import logging.config
import sqlite3
import datetime
from typing import Optional
import aiosqlite

from fastapi import FastAPI, Depends, Response, HTTPException, status
from pydantic import BaseModel

class Enrollment(BaseModel):
    StudentId: int
    ClassId: int

class Class(BaseModel):
    InstructorId: int
    Department: str
    CourseCode: str
    SectionNumber: int
    ClassName: str
    MaxEnrollment: int = 40
    AutomaticEnrollmentFrozen: int = 0

app = FastAPI()

def get_db():
    with contextlib.closing(sqlite3.connect("pro1.db")) as db:
        db.row_factory = sqlite3.Row
        yield db
"""
STUDENTS API ENDPOINTS
"""

# List available classses to students
@app.get("/classes", status_code=status.HTTP_200_OK)
def list_classes(db: sqlite3.Connection = Depends(get_db)):
    classes = db.execute("SELECT * FROM classes where CurrentEnrollment < MaxEnrollment")
    if not classes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Classes not found"
        )
    return {"classes": classes.fetchall()}


# Attempt to enroll in a class
@app.post("/enrollments/", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    enrollment: Enrollment, response: Response, db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("select CurrentEnrollment, MaxEnrollment from Classes where ClassId = ?",[enrollment.ClassId])
    currentEnrollment, maxEnrollment = cur.fetchone()

    # Checking if student is Already enrolled to the course
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ? and dropped = 0",[enrollment.ClassId, enrollment.StudentId])
    sameClasses = cur.fetchall()
    if(sameClasses):
        raise HTTPException(status_code=400, detail="You are already enrolled")
    
    # Checking if Class is full then adding student to waitlist
    if(currentEnrollment >= maxEnrollment):

        # Checking if student is already on waitList
        cur = db.execute("Select * from WaitingLists where ClassId = ? and  StudentId = ?",[enrollment.ClassId, enrollment.StudentId])
        alreadyOnWaitlist = cur.fetchall()
        if(alreadyOnWaitlist):
            raise HTTPException(status_code=400, detail="You are already on waitlist")
  
        # Checking that student is not on more than 3 waitlist (not checked)
        cur = db.execute("Select * from Waitinglists where StudentId = ?",[enrollment.StudentId])
        moreThanThree = cur.fetchall()
        if(len(moreThanThree)>3):
            raise HTTPException(status_code=400, detail="Class is full and You are already on three waitlists so, you can't be placed on a waitlist")
        
        # Adding to the waitlist if waitlist is not full
        cur = db.execute("Select * from Waitinglists where ClassId = ?",[enrollment.ClassId])
        entries = cur.fetchall()
        if(len(entries)>=15):
            raise HTTPException(status_code=400, detail="Waiting List if full for this class")
        waitListPosition = len(entries)+1
        e = dict(enrollment)
        try:
            cur = db.execute(
                """
                INSERT INTO WaitingLists(StudentID,ClassID,WaitingListPos,DateAdded)
                VALUES(?, ?, ? , datetime('now')) 
                """,
                [enrollment.StudentId,enrollment.ClassId,waitListPosition]
            )
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        e["id"] = cur.lastrowid
        response.headers["Location"] = f"/WaitingLists/{e['id']}"
        message = f"Class is full you have been placed on waitlist position {waitListPosition}"
        # Sagar: new function Checking if student was enrolled earlier
        raise HTTPException(status_code=400, detail=message)
    
    # Checking if student was enrolled earlier
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ?",[enrollment.ClassId, enrollment.StudentId])
    entry = cur.fetchone()
    if(entry):
        try:
            db.execute("""
                    UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentId = ?
                    """,
                    [enrollment.ClassId,enrollment.StudentId]) 
            db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment-1),enrollment.ClassId])
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
        return {"success":"Enrolled"}
        
    else:
    # Registering Students if class is not full
        e = dict(enrollment)
        try:
            cur = db.execute(
                """
                INSERT INTO enrollments(StudentId,ClassID,EnrollmentDate)
                VALUES(:StudentId, :ClassId, datetime('now')) 
                """,
                e,
            )
            # db.commit()
            # Updating currentEnrollment
            cur = db.execute("UPDATE Classes SET currentEnrollment = ? where ClassId = ?",[(currentEnrollment+1),enrollment.ClassId])
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        e["id"] = cur.lastrowid
        response.headers["Location"] = f"/enrollments/{e['id']}"
        return {"success":e}

# Delete enrollment of student
@app.delete("/students/{StudentId}/enrollments/{ClassId}")
def drop_enrollment(
    StudentId:int, ClassId:int , db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen from Classes where ClassId = ?",[ClassId])
    entries = cur.fetchone()
    # check if class exists
    if(not entries):
        raise HTTPException(status_code=400, detail="Class does not exist")
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen = entries

    # Checking if student was enrolled to the course
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ? and dropped = 0",[ClassId, StudentId])
    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=400, detail="You are not enrolled in this course")
    # student_dropped = entries['dropped']
     
    # dropping the course
    try:
        db.execute("""
                    UPDATE Enrollments SET dropped = 1 where ClassId = ? and StudentId = ?
                    """,
                    [ClassId,StudentId]) 
        db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment-1),ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    db.commit()
    cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY WaitingListPos ASC",[ClassId])
    entry = cur.fetchone()
    if (not automaticEnrollmentFrozen and (currentEnrollment-1)<maxEnrollment and entry):

        # Enrolling student who is on top of the waitlist
                # Checking if student was enrolled to that course earlier
        cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ?",[ClassId, entry['StudentId']])
        enrollment_entry = cur.fetchone()
        if(enrollment_entry):
            try:
                cur = db.execute("UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentId = ?",[ClassId, entry['StudentId']])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        else:
            try:
                cur = db.execute(
                """
                INSERT INTO enrollments(StudentId,ClassID,EnrollmentDate)
                VALUES(?, ?, datetime('now')) 
                """,
                [entry['StudentId'], ClassId],
            )
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        # updating waitlist positions
        cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY DateAdded ASC",[ClassId])
        entries = cur.fetchall()
        for entry in entries:
            try:
                db.execute("""
                            UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                            """,
                            [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        
        db.commit()
        return  {
                "Message": "successfully dropped"
            }

        
    db.commit()
    return  {
                "Message": "successfully dropped"
            }



# View Waiting List Position
@app.get("/students/{StudentId}/waiting-list/{ClassId}")
def retrieve_position(
    StudentId: int, ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("SELECT * FROM WaitingLists WHERE StudentId = ? and ClassId= ?", [StudentId,ClassId])
    waitingList = cur.fetchone()
    if not waitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        )
    return  {
            "data": waitingList,
            "WaitingListPos":waitingList['WaitingListPos']
            }
    

# Remove from Waiting List
@app.delete("/students/{StudentId}/waiting-list/{ClassId}")
def deleteFromWaitingList(
    StudentId: int, ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    # Checking if entry exist in waitinglist
    cur = db.execute("SELECT * FROM WaitingLists WHERE StudentId = ? and ClassId= ?", [StudentId,ClassId])
    waitingList = cur.fetchone()
    if not waitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not in Waitlist"
        )
     # updating waitlist positions
    try:
        cur = db.execute("Select * from WaitingLists where ClassId = ? and WaitListId > ?",[ClassId, waitingList['WaitListId']])
        entries = cur.fetchall()
        for entry in entries:
            db.execute("""
                        UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                        """,
                        [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
            db.commit()
        db.execute("DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ?", [StudentId,ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
    db.commit()
    return  {
                "Message": "successfully removed from the waiting list"
            }

"""
Instructors API ENDPOINTS
"""

# View Current Enrollment for Their Classes
@app.get("/instructors/{InstructorId}/classes")
def retrieve_Instructors_Classes(
    InstructorId: int, db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("SELECT classname,currentenrollment FROM Classes WHERE InstructorId = ?", [InstructorId])
    instructorClasses = cur.fetchall()
    if not instructorClasses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        )
    return  {
            "instructorClasses": instructorClasses
            }

# View the current waiting list for the course
@app.get("/classes/{ClassId}/wait-list")
def retrieve_Classes_WaitingList(
    ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("SELECT * FROM WaitingLists WHERE ClassId = ?", [ClassId])
    classesWaitingList = cur.fetchall()
    if not classesWaitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        )
    return  {
            "Total Waitlisted Students": len(classesWaitingList),
            "instructorClassesWaitingList": classesWaitingList
            }

# View Students Who Have Dropped the Class
@app.get("/instructors/{ClassId}/dropped-students/")
def retrieve_Instructors_Dropped_Classes(
    ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("SELECT StudentId FROM Enrollments WHERE  ClassId = ? and Dropped = 1", [ClassId])
    studentsWhoDropped = cur.fetchall()
    if not studentsWhoDropped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        )
    return  {
            "DroppedClasses": studentsWhoDropped
            }

# Drop students administratively
# @app.put("/instructors/{ClassId}/drop-student/{StudentId}/")
# def drop_students_administratively(
#     ClassId:int, StudentId:int, db: sqlite3.Connection = Depends(get_db)
# ):
#     try:
#         db.execute("UPDATE Enrollments SET dropped = 1 where ClassId = ? and StudentId = ?", [ClassId, StudentId])
#         db.commit()
#     except sqlite3.IntegrityError as e:
#         db.rollback()
#         raise HTTPException(
#                 status_code=status.HTTP_409_CONFLICT,
#                 detail={"type": type(e).__name__, "msg": str(e), "status":"dropped failed"},
#             )
#     return  {
#             "status": "Dropped Successfully"
#             }


#### Registrar's API Endpoints ####

# Add New Classes and Sections
@app.post("/classes/", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    class_: Class, response: Response, db: sqlite3.Connection = Depends(get_db)
):
    
    # checking if same class and section exist
    cur = db.execute("Select * from classes where ClassName = ? and SectionNumber = ?",[class_.ClassName, class_.SectionNumber])
    entry = cur.fetchone()
    newClassId = 0
    if(entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Already Exist',
            )
    try:
        cur = db.execute(
            """
            INSERT INTO Classes(InstructorId,Department,CourseCode,SectionNumber,
            ClassName,CurrentEnrollment,MaxEnrollment,AutomaticEnrollmentFrozen)
            VALUES(?, ?, ? , ?, ?, 0, ?, ?) 
            """,
                [class_.InstructorId,class_.Department,class_.CourseCode,class_.SectionNumber,
                class_.ClassName,class_.MaxEnrollment,class_.AutomaticEnrollmentFrozen]
            )
        newClassId = cur.lastrowid
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
        status_code=status.HTTP_40, 
        detail={"type": type(e).__name__, "msg": str(e)},
        )
    response.headers["Location"] = f"/classes/{newClassId}"
    return {'status':"Class created successfully"}

@app.delete("/classes/{ClassId}",status_code=status.HTTP_200_OK)
def drop_enrollment(
    ClassId:int , db: sqlite3.Connection = Depends(get_db)
):
    # checking if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    try:
        db.execute(
            """
            DELETE FROM Classes WHERE ClassId= ? 
            """,
            [ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Class Deleted Successfully"}