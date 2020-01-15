CREATE DATABASE IF NOT EXISTS TEX COLLATE utf8_general_ci;
USE TEX;

CREATE TABLE IF NOT EXISTS keywords(
	keyword VARCHAR(60) NOT NULL, 
	basic_notation VARCHAR(60),
    kind VARCHAR(60) NOT NULL,
    UNIQUE INDEX(keyword),
	INDEX(kind, basic_notation)
);

CREATE TABLE IF NOT EXISTS constraints(
	constraint_word VARCHAR(60) NOT NULL,
    kind VARCHAR(60),
    notation VARCHAR(60),
    path INT NOT NULL,
    nested_constraint VARCHAR(60),
    INDEX(constraint_word, kind, notation, path),
    FOREIGN KEY(kind) 
		REFERENCES keywords(kind)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conditions(
	kind VARCHAR(60) NOT NULL,
	previous VARCHAR(60),
	notation1 VARCHAR(60),
	following VARCHAR(60),
	notation2 VARCHAR(60),
    will_change INT,
    constraint_word VARCHAR(60),
	path INT,
	INDEX(kind, will_change,
		previous, notation1, 
		following, notation2,
        constraint_word, path),
	FOREIGN KEY (kind)
		REFERENCES keywords(kind)
		ON UPDATE CASCADE ON DELETE CASCADE,
	FOREIGN KEY (constraint_word)
		REFERENCES constraints(constraint_word)
		ON UPDATE CASCADE ON DELETE CASCADE
);

LOAD DATA LOCAL INFILE '~/PycharmProjects/course_work/database/keywords' INTO TABLE keywords;
LOAD DATA LOCAL INFILE '~/PycharmProjects/course_work/database/constraints' INTO TABLE constraints;
LOAD DATA LOCAL INFILE '~/PycharmProjects/course_work/database/conditions' INTO TABLE conditions;

USE TEX;
SET SQL_SAFE_UPDATES = 0;
DELETE FROM conditions;
DELETE FROM constraints;
DELETE FROM keywords;
SELECT * FROM conditions;
#drop database TEX;
select * from constraints where kind = 'сумма';
