from dataclasses import dataclass
import datetime
from typing import List
import asyncpg


@dataclass
class Examination:
    id: int
    patient_id: int
    date: datetime.date = datetime.date.today()
    summary: str = None
    details: str = None

    @classmethod
    def build_from_record(cls, record):
        return cls(id=record['id'], date=record['date'], summary=record['summary'], details=record['details'], patient_id=record['patient_id'])

    async def amend(self, *, con: asyncpg.Connection, summary=None, details=None):
        data = []
        if summary is not None:
            data.append({'summary': summary})
        if details is not None:
            data.append({'details': details})
        if not data:
            return
        query = f"UPDATE examinations SET {', '.join(f'{x} = ${i + 2}' for i, x in enumerate(data.keys()))} WHERE id = $1 RETURNING *;"
        rec = await con.fetchrow(query, self.id *data.values())
        self = self.build_from_record(rec)
        return self

@dataclass
class Person:
    id: int
    name: str
    age: int
    sex: str
    occupation: str

    @classmethod
    def build_from_record(cls, record):
        """Override in subclasses"""
        return cls(record['id'], record['name'], record['age'], record['sex'], record['occupation'])


@dataclass
class Patient(Person):
    doa: datetime.date
    next_of_kin_id: int
    next_of_kin: Person = None
    history: List[Examination] = None

    def __post_init__(self):
        if self.history is None:
            self.history = []

    @classmethod
    def build_from_record(cls, record):
        self = Person.build_from_record(record)
        self.doa = record['date_of_admission']
        self.next_of_kin_id = record['next_of_kin_id']
        return cls(**self.__dict__)

    async def get_next_of_kin(self, con: asyncpg.Connection):
        if self.next_of_kin is not None:
            return self.next_of_kin
        query = 'SELECT * FROM relations WHERE id = $1;'
        record = await con.fetchrow(query, self.next_of_kin_id)
        self.next_of_kin = Person.build_from_record(record)
        return self.next_of_kin

    async def fetch_history(self, con: asyncpg.Connection):
        if self.history:
            return self.history
        query = 'SELECT * FROM examinations WHERE patient_id = $1 ORDER BY date DESC;'
        records = await con.fetch(query, self.id)
        self.history = [Examination.build_from_record(record) for record in records]
        return self.history

    async def add_exam(self, summary: str, details: str, date: datetime.date = None, *, con: asyncpg.Connection):
        if self.history is None:
            await self.fetch_history(con=con)
        date = date or datetime.date.today()
        query = 'INSERT INTO examinations (patient_id, date, summary, details) VALUES ($1, $2, $3, $4) RETURNING *;'
        record = await con.fetchrow(query, self.id, date, summary, details)
        self.history.insert(0, Examination.build_from_record(record))
        return self.history
