# Security baseline

Keep secrets outside source control and replace the development JWT secret before deployment. Passwords are hashed with Argon2 through pwdlib. Public registration only assigns the farmer role; privileged roles require a separate administrative process. Add authorization and organization isolation to every protected business endpoint as those modules are introduced. Use HTTPS, trusted CORS origins, upload validation, authentication rate limits, backups and tested restoration. Never log passwords or bearer tokens.

This initial baseline is not a completed security audit.
