"""MCP-Werkzeuge (WIKI-78): eine KI sucht und liest in der Bibliothek über das Model Context Protocol. Ein Werkzeug ist
eine dünne Schicht über den Diensten der App (Bibliothek, Suche, Lesen) mit geprüfter Eingabe (Pydantic); der Weg
`POST /api/v1/mcp` spricht MCP über HTTP (zustandslos, Antworten als JSON) hinter derselben Anmeldung wie alle Wege."""
