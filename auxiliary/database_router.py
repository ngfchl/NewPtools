from auxiliary.settings import DATABASE_APPS_MAPPING


class DatabaseAppsRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the auth and contenttypes apps only appear in the
        'auth_db' database.
        """
        if app_label in DATABASE_APPS_MAPPING:
            return db == DATABASE_APPS_MAPPING[app_label]
        return None
