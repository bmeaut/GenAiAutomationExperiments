#Feladat:
- Sablon alapján sok emailt előkészítő script/makró: egy placeholdereket tartalmazó email sablon és egy beszúrandó szövegeket és email címeket tartalmazó táblázat alapján a makró a táblázat minden sorához feldob egy email ablakot kitöltve, hogy már csak a "Küldés"-re kelljen rákattintani. Példa felhasználás: minden hallgatónak névre szóló e-mail arról, hogy ne felejtse el kitölteni a záróvizsga adatlapot. Továbbfejlesztés: a táblázat egyik mezője azt határozza meg, hogy több lehetséges sablon közül melyiket használja a makró. Pl. szakdolgozat és diplomaterv esetében kicsit eltérnek a teendők. És a sablon kiválasztó mező lehet üres is, akkor arra a sorra nem készül email.

Munkafolyamat:
 első generálás rossz, kamuzott nem valódi world dokumentumokat generált ki a temapltekbe helyes a behelyettesítés.

 egy word template manuális elkészítése után felismerte hogy milyen könyvtárakat kell hasznbálni, a fájl kezelét kitöltést helyesen megoldotta py sciptel

 Kövi lépések:

 összerakni az autoata kiküldést, tesztek generálása ellenőrzése, elkészíteni VBA-val is