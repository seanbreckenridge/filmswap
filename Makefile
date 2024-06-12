# to use these 'pip install babel'
# hmm, some weirdness going on with modtimes, but it builds good-enough
# if stuff breaks and it doent seem to be building, just make clean && make

SOURCE_FILES := $(shell find ./filmswap -type f -iname '*.py')

all: init build

init:
	@@ [ -d ./locales/en_US/LC_MESSAGES/ ] || mkdir ./locales/en_US/LC_MESSAGES -p

# if adding a new locale, add the resulting binary path in locales here
build: ./locales/en_US/LC_MESSAGES/film.mo ./locales/en_US/LC_MESSAGES/manga.mo
	tree ./messages ./locales

# MANGA

./messages/manga.pot: ./messages/reference.pot
	msgmerge -U --backup=off ./messages/manga.pot ./messages/reference.pot
	touch ./messages/manga.pot

./locales/en_US/LC_MESSAGES/manga.mo: ./messages/manga.pot
	pybabel compile -i ./messages/manga.pot -o ./locales/en_US/LC_MESSAGES/manga.mo

# FILM

./messages/film.pot: ./messages/reference.pot
	msgmerge -U --backup=off ./messages/film.pot ./messages/reference.pot
	touch ./messages/film.pot

./locales/en_US/LC_MESSAGES/film.mo: ./messages/film.pot
	pybabel compile -i ./messages/film.pot -o ./locales/en_US/LC_MESSAGES/film.mo

# REFERENCE FILE

./messages/reference.pot: $(SOURCE_FILES) .env
	pybabel extract -o ./messages/reference.pot ./filmswap/

clean:
	rm -rf ./locales
