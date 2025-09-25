# 3. heti "Work Out Loud"
## Mivel foglalkoztam eddig
Python tool készítése, ami:
- népszerű, sokat tesztelt Python git repók commitjain végighalad, szűri a javításokat, majd elmenti a javítás előtti és utána lévő verziókat
- keres említett issue (bug) jelentéseket
- létrehoz egy szeparált Python környezetet, ahol minden fejlesztéshez szüksékes függőséget próbál telepíteni
- kódmetrikákat mér
- javítás utáni verzióra lefuttatja a saját tesztjeit
- javítás előtti verzióra készít egy promptot, amire kapott LLM válasz (egyelőre kézzel) egy diff-et tartalmaz, ami javítani próbálja a bugot, majd erre is lefuttatja a teszteket
- amit csak lehet információt elment .csv, .log fájlokba

## Mivel fogok foglalkozni jövő héten
- javítani a projektekhez tartozó saját tesztkörnyezetek telepítését, még sok a hiba
- LLM API használatnak utánanézni
- promptba kerülő kontextus szűkítése, hogy kevesebb tokenbe kerüljön 1-1 javítási próbálkozás
- mutation testing is kerüljön a saját test suite mellé?