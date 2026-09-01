from sqlalchemy.orm import Session

from src.models.script import Script


class ScriptRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        project_id: str,
        raw_text: str,
        source_format: str,
        original_filename: str | None,
    ) -> Script:
        script = Script(
            project_id=project_id,
            raw_text=raw_text,
            source_format=source_format,
            original_filename=original_filename,
        )
        self._db.add(script)
        self._db.commit()
        self._db.refresh(script)
        return script
