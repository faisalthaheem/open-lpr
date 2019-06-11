db.createUser(
    {
        user: "lpr",
        pwd: "lpr",
        roles: [
            {
                role: "readWrite",
                db: "openlpr"
            }
        ]
    }
);