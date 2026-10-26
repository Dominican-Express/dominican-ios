-- Dominican Express — el encubrimiento
--
-- Después de 02_attack y del barrido (03_detect), las mulas borran el rastro.
-- Tras esto, el grafo ACTUAL ya no enseña el fraude; `fn::investigate` sobre
-- una alerta lo reconstruye tal como estaba cuando saltó (09_time_travel).

-- 1. Dan de baja el móvil que compartían las cuatro identidades.
DELETE uses WHERE out = device:mula;
DELETE device:mula;

-- 2. Luis deja de ser cotitular de la cuenta de Ana.
DELETE owns WHERE in = customer:luis AND out = account:ana;

-- 3. Marta vacía su cuenta hacia otro banco. Pasa por fn::transfer, así que
--    el libro lo recoge: el dinero que sale nunca se borra.
LET $b = (SELECT VALUE balance FROM ONLY account:marta);
RETURN fn::transfer(account:marta, account:ext, $b);
