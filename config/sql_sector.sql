SELECT c.codi AS codi, c.descripcio AS descr,
    ST_Area(ST_Intersection(c.geom, p.geom)) AS area_int,
    (ST_Area(ST_Intersection(c.geom, p.geom)) / p.area) * 100 as per_int
FROM planejament_urba.sectors_urbanistics AS c, carto.parcela as p
WHERE p.ninterno = $ID_VALUE
    AND ST_Intersects(p.geom, c.geom)
ORDER BY ST_Area(ST_Intersection(c.geom, p.geom)) DESC
LIMIT 3