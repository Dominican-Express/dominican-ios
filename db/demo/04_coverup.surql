-- Dominican Express — el encubrimiento DESDE DENTRO
--
-- Las mulas, como clientes, ya no pueden borrar nada (10_controls: los
-- permisos lo impiden, desvincular un aparato deja `ended_at` y la cuenta del
-- anillo está congelada; lo enseña `coverup.py`). Lo que queda es alguien con
-- acceso de ADMINISTRADOR (root): un empleado cómplice. Esto es lo que haría.
-- La auditoría lo recoge todo, con lo que había antes de cada borrado, y
-- `fn::investigate` (09) reconstruye el grafo de la alerta.

-- 1. Borra el móvil que compartían las cuatro identidades.
DELETE uses WHERE out = device:mula;
DELETE device:mula;

-- 2. Quita a Luis como cotitular de la cuenta de Ana.
DELETE owns WHERE in = customer:luis AND out = account:ana;

-- 3. Descongela la cuenta de Marta y la vacía hacia otro banco. Pasa por
--    fn::transfer, así que el libro lo recoge: el dinero que sale nunca se borra.
RETURN fn::release_account(account:marta, 'liberada sin caso');
LET $b = (SELECT VALUE balance FROM ONLY account:marta);
RETURN fn::transfer(account:marta, account:ext, $b);
