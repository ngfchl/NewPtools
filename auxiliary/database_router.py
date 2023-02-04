from auxiliary.settings import DATABASE_APPS_MAPPING


class DatabaseAppsRouter:

    def db_for_read(self, model, **hints):
        """Point all read operations to the specific database."""
        if model._meta.app_label in DATABASE_APPS_MAPPING:
            return DATABASE_APPS_MAPPING[model._meta.app_label]
        return None

    def db_for_write(self, model, **hints):
        """Point all write operations to the specific database."""
        if model._meta.app_label in DATABASE_APPS_MAPPING:
            return DATABASE_APPS_MAPPING[model._meta.app_label]
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the auth and contenttypes apps only appear in the
        'auth_db' database.
        """
        if app_label in DATABASE_APPS_MAPPING:
            return db == DATABASE_APPS_MAPPING[app_label]
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the auth or contenttypes apps is
        involved.
        """
        # db_obj1 = DATABASE_APPS_MAPPING.get(obj1._meta.app_label)
        # db_obj2 = DATABASE_APPS_MAPPING.get(obj2._meta.app_label)
        # if db_obj1 or db_obj2:
        #     return True
        return True
