class PrimaryReplicaRouter:
    """
    Database router for Enterprise scale Morpheus.
    Routes all read operations (SELECT) to read replicas,
    and all write operations (INSERT/UPDATE/DELETE) to the primary default DB.
    """

    def db_for_read(self, model, **hints):
        """
        Reads go to a randomly selected replica, if available.
        If 'replica' is not configured, it safely falls back to 'default'.
        """
        from django.conf import settings

        if 'replica' in settings.DATABASES:
            return 'replica'
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Writes always go to the primary database.
        """
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Relations between objects are allowed if they are both in primary/replica pool.
        """
        db_set = {'default', 'replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Migrations are only ever applied to the primary database.
        Replicas are read-only and sync via streaming replication at the infrastructure level.
        """
        return db == 'default'
