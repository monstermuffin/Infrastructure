# Cloudflare Tunnel token deploy.

Local config not used as attempts to do this was painful. Turns out local config pushing is not as simple as pushing the endpoint via a config file, need to do the whole DNS registration thing and have a token that does all the zones etc etc.

Moved tunnel config to Terraform instead, this deploys the connector itself which is all that's needed.