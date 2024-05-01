-- SQLite migration file
-- Modify the length of the letter and gift columns in the swap_users table
--
-- need to copy the entire schema here since sqlite alter varchar stuff

PRAGMA foreign_keys=off;

BEGIN TRANSACTION;

-- Create a temporary table with the modified schema
CREATE TABLE swap_users_temp (
    id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    name VARCHAR(32) NOT NULL, 
    letter VARCHAR(4000), 
    gift VARCHAR(4000), 
    done_watching BOOLEAN NOT NULL, 
    santa_id INTEGER, 
    giftee_id INTEGER, 
    letterboxd_username VARCHAR(64), 
    PRIMARY KEY (id)
);

-- Copy data from the original table to the temporary table
INSERT INTO swap_users_temp (id, user_id, name, letter, gift, done_watching, santa_id, giftee_id, letterboxd_username)
SELECT id, user_id, name, letter, gift, done_watching, santa_id, giftee_id, letterboxd_username FROM swap_users;

-- Drop the original table
DROP TABLE swap_users;

-- Rename the temporary table to the original table name
ALTER TABLE swap_users_temp RENAME TO swap_users;

COMMIT;

PRAGMA foreign_keys=on;
