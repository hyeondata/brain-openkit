# Development and holdout queries

Write relevance labels before inspecting model rankings. Use development queries to choose settings, then freeze the settings before running the holdout set. Changing thresholds after seeing holdout errors leaks evaluation information. A query split can share the same document collection; it is different from holding out entire documents.
