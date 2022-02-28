SELECT q.codi AS qua_codi, q.descripcio AS qua_descripcio, ST_Area(ST_Multi(ST_Intersection(p.geom, q.geom))) AS area_int,
       (ST_Area(ST_Multi(ST_Intersection(p.geom, q.geom))) / p.area)*100 as per_int, 
       -- Qualificació General
       qg.tipus_qualif AS qg_tipus, qg.subzona AS qg_subzona, qg.definicio AS qg_definicio, 
       -- Tipus Ordenació
       tord.cod_ord AS tord_codi, tord.tipus_ord AS tord_descripcio, 
       -- Usos
       u.hab_unifamiliar, u.hab_plurifamiliar, u.hab_rural, u.res_especial,
       u.res_mobil, u.hoteler, u.com_petit, u.com_mitja, u.com_gran,
       u.oficines_serveis, u.restauracio, u.recreatiu, u.magatzem, u.industrial_1, u.industrial_2, u.industrial_3, u.industrial_4, u.industrial_5,
       u.taller_reparacio, u.educatiu, u.sanitari, u.assistencial, u.cultural, u.associatiu, u.esportiu, u.serveis_publics, u.serveis_tecnics,
       u.serveis_ambientals, u.serveis_radio, u.aparcament, u.estacions_servei, u.agricola, u.ramader, u.forestal, u.lleure, u.ecologic,
       -- Condicions edificació
       ce.fondaria_edif, ce.edificabilitat, ce.ocupacio, ce.densitat_hab, ce.vol_max_edif, ce.fondaria_edif_pb, ce.pb, ce.alcada, ce.punt_aplic, ce.sep_min, 
       ce.constr_aux_alcada, ce.constr_aux_ocupacio, ce.tanques, ce.nplantes, ce.alcada_lliure, ce.entresol_pb, ce.sotacoberta, ce.pendent,
       ce.terrasses, ce.elem_sort, ce.cossos_sort, ce.cossos_annexes, ce.porxos, ce.tract_facana, ce.comp_facana, ce.prop_obertura, ce.material_facana,
       ce.material_coberta, ce.fusteria, ce.espai_lliure, ce.altell, ce.altres, 
       -- Condicions de parcela cp.prof_min
       cp.front_min, cp.parce_min, cp.prof_min, cp.circum_finsc
  FROM cadsatre.parcela AS p, planejament_urba.qualificacio AS q
       INNER JOIN planejament_urba.qualificacio_general AS qg ON q.codi = qg.id
       LEFT JOIN planejament_urba.tipus_ordenacio AS tord ON qg.cod_ord = tord.cod_ord
       LEFT JOIN planejament_urba.usos as u ON qg.id = u.id
       LEFT JOIN planejament_urba.condicions_edif as ce ON qg.id = ce.id
       LEFT JOIN planejament_urba.condicions_parce as cp ON qg.id = cp.id
  WHERE p.ninterno = $ID_VALUE
        AND ST_Intersects(p.geom, q.geom)
  ORDER BY area_int DESC
  LIMIT 4
