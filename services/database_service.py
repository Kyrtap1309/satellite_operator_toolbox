import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, desc

from models.database import DatabaseManager, TLEDataModel
from models.satellite import TLEData


class DatabaseService:
    """Service for database operations."""

    def __init__(self, database_manager: DatabaseManager):
        self.db_manager = database_manager
        self.logger = logging.getLogger(__name__)

    def save_tle_data(self, tle_data: TLEData, source: str = "unknown") -> bool:
        """Save TLE data to database."""
        try:
            with self.db_manager.get_session() as session:
                # Upewnij się, że norad_id jest stringiem
                norad_id_str = str(tle_data.norad_id)

                # Parse TLE line 1 to extract epoch and other orbital elements
                line1_parts = tle_data.tle_line1.split()
                line2_parts = tle_data.tle_line2.split()

                # Sprawdź czy linie TLE mają wystarczającą długość
                if len(line1_parts) < 8:
                    self.logger.error(f"TLE Line 1 has insufficient parts: {len(line1_parts)}")
                    return False

                if len(line2_parts) < 8:
                    self.logger.error(f"TLE Line 2 has insufficient parts: {len(line2_parts)}")
                    return False

                # Extract epoch from TLE - bezpieczne parsowanie
                try:
                    epoch_str = line1_parts[3]
                    year = int("20" + epoch_str[:2]) if int(epoch_str[:2]) < 57 else int("19" + epoch_str[:2])
                    day_of_year = float(epoch_str[2:])
                    epoch = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
                except (ValueError, IndexError) as e:
                    self.logger.error(f"Error parsing epoch from TLE: {e}")
                    epoch = datetime.utcnow()  # Fallback to current time

                # Check if this exact TLE already exists
                existing = (
                    session.query(TLEDataModel)
                    .filter(
                        and_(
                            TLEDataModel.norad_id == norad_id_str,
                            TLEDataModel.tle_line1 == tle_data.tle_line1,
                            TLEDataModel.tle_line2 == tle_data.tle_line2,
                        )
                    )
                    .first()
                )

                if existing:
                    self.logger.debug(f"TLE data already exists for NORAD ID {norad_id_str}")
                    return True

                # Bezpieczne parsowanie parametrów orbitalnych z obsługą notacji naukowej
                try:
                    mean_motion = float(line2_parts[7]) if len(line2_parts) > 7 else 0.0
                    eccentricity = float("0." + line2_parts[4]) if len(line2_parts) > 4 else 0.0
                    inclination = float(line2_parts[2]) if len(line2_parts) > 2 else 0.0
                    arg_of_perigee = float(line2_parts[5]) if len(line2_parts) > 5 else 0.0
                    raan = float(line2_parts[3]) if len(line2_parts) > 3 else 0.0
                    mean_anomaly = float(line2_parts[6]) if len(line2_parts) > 6 else 0.0

                    # Parsowanie elementów z line1 - bezpieczniej
                    if len(line1_parts) > 7:
                        rev_at_epoch_str = line1_parts[7]
                        # Usuń ostatnią cyfrę (checksum)
                        rev_at_epoch = int(rev_at_epoch_str[:-1]) if rev_at_epoch_str[:-1].isdigit() else 0
                    else:
                        rev_at_epoch = 0

                    classification = line1_parts[1][7] if len(line1_parts) > 1 and len(line1_parts[1]) > 7 else "U"
                    international_designator = line1_parts[2] if len(line1_parts) > 2 else ""

                    if len(line1_parts) > 6:
                        ephemeris_type_str = line1_parts[6]
                        # Ostatnia cyfra to typ efemeryd
                        ephemeris_type = (
                            int(ephemeris_type_str[-1])
                            if ephemeris_type_str and ephemeris_type_str[-1].isdigit()
                            else 0
                        )
                    else:
                        ephemeris_type = 0

                except (ValueError, IndexError) as e:
                    self.logger.error(f"Error parsing orbital parameters: {e}")
                    # Ustaw wartości domyślne
                    mean_motion = 0.0
                    eccentricity = 0.0
                    inclination = 0.0
                    arg_of_perigee = 0.0
                    raan = 0.0
                    mean_anomaly = 0.0
                    rev_at_epoch = 0
                    classification = "U"
                    international_designator = ""
                    ephemeris_type = 0

                # Create new TLE record
                tle_model = TLEDataModel(
                    norad_id=norad_id_str,  # Ensure string
                    satellite_name=tle_data.satellite_name,
                    tle_line1=tle_data.tle_line1,
                    tle_line2=tle_data.tle_line2,
                    epoch=epoch,
                    mean_motion=mean_motion,
                    eccentricity=eccentricity,
                    inclination=inclination,
                    arg_of_perigee=arg_of_perigee,
                    raan=raan,
                    mean_anomaly=mean_anomaly,
                    rev_at_epoch=rev_at_epoch,
                    classification=classification,
                    international_designator=international_designator,
                    ephemeris_type=ephemeris_type,
                    source=source,
                )

                session.add(tle_model)
                session.commit()

                self.logger.info(f"Saved TLE data for {tle_data.satellite_name} (NORAD {norad_id_str})")
                return True

        except Exception as e:
            self.logger.error(f"Error saving TLE data: {e}")
            return False

    def get_latest_tle(self, norad_id: str) -> Optional[TLEData]:
        """Get latest TLE for a satellite."""
        try:
            # Upewnij się, że norad_id jest stringiem
            norad_id_str = str(norad_id)

            with self.db_manager.get_session() as session:
                latest = (
                    session.query(TLEDataModel)
                    .filter(TLEDataModel.norad_id == norad_id_str)
                    .order_by(desc(TLEDataModel.epoch))
                    .first()
                )

                if latest:
                    # NAPRAWIONE: przekaż wszystkie wymagane argumenty
                    return TLEData(
                        satellite_name=latest.satellite_name,
                        norad_id=latest.norad_id,
                        tle_line1=latest.tle_line1,
                        tle_line2=latest.tle_line2,
                        epoch=latest.epoch.isoformat() if latest.epoch else "",
                        mean_motion=latest.mean_motion or 0.0,
                        eccentricity=latest.eccentricity or 0.0,
                        inclination=latest.inclination or 0.0,
                        ra_of_asc_node=latest.raan or 0.0,
                        arg_of_pericenter=latest.arg_of_perigee or 0.0,
                        mean_anomaly=latest.mean_anomaly or 0.0,
                        classification=latest.classification,
                        intl_designator=latest.international_designator,
                        element_set_no=latest.element_set_no,
                        rev_at_epoch=latest.rev_at_epoch,
                        bstar=latest.bstar,
                        mean_motion_dot=None,  # Nie zapisujemy tego w bazie
                        mean_motion_ddot=None,  # Nie zapisujemy tego w bazie
                        period_minutes=1440.0 / latest.mean_motion
                        if latest.mean_motion and latest.mean_motion > 0
                        else None,
                    )
                return None

        except Exception as e:
            self.logger.error(f"Error getting latest TLE: {e}")
            return None

    def get_tle_history(self, norad_id: str, days_back: int = 30) -> List[TLEData]:
        """Get TLE history for a satellite."""
        try:
            # Upewnij się, że norad_id jest stringiem
            norad_id_str = str(norad_id)
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            self.logger.debug(f"Querying TLE history for NORAD {norad_id_str}, cutoff date: {cutoff_date}")

            with self.db_manager.get_session() as session:
                history = (
                    session.query(TLEDataModel)
                    .filter(and_(TLEDataModel.norad_id == norad_id_str, TLEDataModel.epoch >= cutoff_date))
                    .order_by(desc(TLEDataModel.epoch))
                    .all()
                )

                self.logger.debug(f"Found {len(history)} TLE records in database for NORAD {norad_id_str}")

                result = []
                for tle in history:
                    # NAPRAWIONE: przekaż wszystkie wymagane argumenty
                    tle_data = TLEData(
                        satellite_name=tle.satellite_name,
                        norad_id=tle.norad_id,
                        tle_line1=tle.tle_line1,
                        tle_line2=tle.tle_line2,
                        epoch=tle.epoch.isoformat() if tle.epoch else "",
                        mean_motion=tle.mean_motion or 0.0,
                        eccentricity=tle.eccentricity or 0.0,
                        inclination=tle.inclination or 0.0,
                        ra_of_asc_node=tle.raan or 0.0,
                        arg_of_pericenter=tle.arg_of_perigee or 0.0,
                        mean_anomaly=tle.mean_anomaly or 0.0,
                        classification=tle.classification,
                        intl_designator=tle.international_designator,
                        element_set_no=tle.element_set_no,
                        rev_at_epoch=tle.rev_at_epoch,
                        bstar=tle.bstar,
                        mean_motion_dot=None,
                        mean_motion_ddot=None,
                        period_minutes=1440.0 / tle.mean_motion if tle.mean_motion and tle.mean_motion > 0 else None,
                    )
                    result.append(tle_data)

                self.logger.info(f"Returning {len(result)} TLE records for NORAD {norad_id_str}")
                return result

        except Exception as e:
            self.logger.error(f"Error getting TLE history: {e}")
            return []

    def get_tle_coverage_info(self, norad_id: str, days_back: int = 30) -> dict:
        """Get information about TLE data coverage in database."""
        try:
            norad_id_str = str(norad_id)
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            with self.db_manager.get_session() as session:
                # Zlicz rekordy w zadanym okresie
                count = (
                    session.query(TLEDataModel)
                    .filter(and_(TLEDataModel.norad_id == norad_id_str, TLEDataModel.epoch >= cutoff_date))
                    .count()
                )

                # Znajdź najstarszy i najnowszy rekord w okresie
                oldest = (
                    session.query(TLEDataModel)
                    .filter(and_(TLEDataModel.norad_id == norad_id_str, TLEDataModel.epoch >= cutoff_date))
                    .order_by(TLEDataModel.epoch.asc())
                    .first()
                )

                newest = (
                    session.query(TLEDataModel)
                    .filter(and_(TLEDataModel.norad_id == norad_id_str, TLEDataModel.epoch >= cutoff_date))
                    .order_by(TLEDataModel.epoch.desc())
                    .first()
                )

                coverage_days = 0
                if oldest and newest:
                    coverage_days = (newest.epoch - oldest.epoch).days + 1

                return {
                    "record_count": count,
                    "coverage_days": coverage_days,
                    "requested_days": days_back,
                    "has_complete_coverage": coverage_days >= days_back,
                    "oldest_epoch": oldest.epoch if oldest else None,
                    "newest_epoch": newest.epoch if newest else None,
                }

        except Exception as e:
            self.logger.error(f"Error getting TLE coverage info: {e}")
            return {
                "record_count": 0,
                "coverage_days": 0,
                "requested_days": days_back,
                "has_complete_coverage": False,
                "oldest_epoch": None,
                "newest_epoch": None,
            }

    def cleanup_old_tles(self, days_to_keep: int = 90) -> int:
        """Remove TLE data older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            with self.db_manager.get_session() as session:
                deleted = session.query(TLEDataModel).filter(TLEDataModel.created_at < cutoff_date).delete()

                session.commit()
                self.logger.info(f"Cleaned up {deleted} old TLE records")
                return deleted

        except Exception as e:
            self.logger.error(f"Error cleaning up old TLEs: {e}")
            return 0

    def get_satellite_list(self) -> list[dict]:
        """Get list of satellites with TLE data."""
        try:
            with self.db_manager.get_session() as session:
                satellites = session.query(TLEDataModel.norad_id, TLEDataModel.satellite_name).distinct().all()

                return [{"norad_id": sat.norad_id, "name": sat.satellite_name} for sat in satellites]

        except Exception as e:
            self.logger.error(f"Error getting satellite list: {e}")
            return []
