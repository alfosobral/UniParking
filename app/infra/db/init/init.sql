create table if not exists users(
document_id serial primary key,
email text unique not null,
user_name text not null,
user_surname text not null,
phone text unique not null
);

create table if not exists cars(
plate text primary key,
id_owner serial not null,
car_type text not null default 'GENERAL',
constraint car_owner foreign key (id_owner) references users (document_id)
);

create table if not exists spots(
spot_code text primary key,
occupied boolean not null,
x_coord int not null,
y_coord int not null,
spot_type text not null default 'GENERAL'
);

create table if not exists allocation(
spot_code text primary key,
assigned_plate text not null,
assigned_at timestamptz not null,
constraint spot_code foreign key (spot_code) references spots (spot_code),
constraint assigned_plate foreign key (assigned_plate) references cars (plate)
);

-- (Opcional pero MUY recomendable) FK para asegurar que el spot exista
ALTER TABLE public.allocation
  ADD CONSTRAINT fk_allocation_spot
  FOREIGN KEY (spot_code) REFERENCES public.spots(spot_code)
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- (Opcional) default para assigned_at
ALTER TABLE public.allocation
  ALTER COLUMN assigned_at SET DEFAULT now();

-- 1) Función del trigger
DROP FUNCTION IF EXISTS public.fn_allocation_occupy_spot() CASCADE;

CREATE OR REPLACE FUNCTION public.fn_allocation_occupy_spot()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $func$
BEGIN
  -- Ocupar el spot SOLO si está libre. Esto además bloquea la fila ≈ safe para concurrencia
  UPDATE public.spots
     SET occupied = true
   WHERE spot_code = NEW.spot_code
     AND occupied = false;

  IF NOT FOUND THEN
    -- Si no actualizó, el spot no existe (si no pusiste FK) o ya está ocupado
    RAISE EXCEPTION 'Spot % no disponible (inexistente o ya ocupado)', NEW.spot_code
      USING ERRCODE = 'check_violation';
  END IF;

  -- Aseguramos assigned_at si venía null
  IF NEW.assigned_at IS NULL THEN
    NEW.assigned_at := now();
  END IF;

  RETURN NEW;  -- al ser BEFORE INSERT devolvemos la fila a insertar
END;
$func$;

-- 2) Trigger en allocation (solo INSERT)
DROP TRIGGER IF EXISTS trg_allocation_before_insert ON public.allocation;

CREATE TRIGGER trg_allocation_before_insert
BEFORE INSERT ON public.allocation
FOR EACH ROW
EXECUTE FUNCTION public.fn_allocation_occupy_spot();

-- 1) Función para liberar el spot al borrar la asignación
DROP FUNCTION IF EXISTS public.fn_allocation_release_spot() CASCADE;

CREATE OR REPLACE FUNCTION public.fn_allocation_release_spot()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $func$
BEGIN
  -- Liberar el spot (si ya estaba libre no pasa nada)
  UPDATE public.spots
     SET occupied = false
   WHERE spot_code = OLD.spot_code
     AND occupied = true;

  RETURN OLD; -- en BEFORE/AFTER DELETE se retorna OLD
END;
$func$;

-- 2) Trigger en allocation (DELETE)
DROP TRIGGER IF EXISTS trg_allocation_before_delete ON public.allocation;

CREATE TRIGGER trg_allocation_before_delete
BEFORE DELETE ON public.allocation
FOR EACH ROW
EXECUTE FUNCTION public.fn_allocation_release_spot();

-- =========================================
-- USERS
-- =========================================
INSERT INTO users (email, user_name, user_surname, phone)
VALUES
  ('juan.perez@example.com', 'Juan', 'Pérez', '099111111'),
  ('maria.garcia@example.com', 'María', 'García', '099222222'),
  ('lucas.fernandez@example.com', 'Lucas', 'Fernández', '099333333'),
  ('sofia.lopez@example.com', 'Sofía', 'López', '099444444');

-- =========================================
-- CARS
-- =========================================
INSERT INTO cars (plate, id_owner, car_type)
VALUES
  ('ABC123', 1, 'GENERAL'),
  ('XYZ987', 2, 'DISABLED'),
  ('LMN456', 3, 'GENERAL'),
  ('JKL222', 4, 'GENERAL');

-- =========================================
-- SPOTS
-- =========================================
INSERT INTO spots (spot_code, occupied, x_coord, y_coord, spot_type)
VALUES
  ('A1', false, 10, 20, 'GENERAL'),
  ('A2', false, 15, 20, 'GENERAL'),
  ('A3', false, 20, 20, 'GENERAL'),
  ('B1', false, 10, 30, 'DISABLED'),
  ('B2', true, 15, 30, 'DISABLED'),
  ('C1', false, 10, 40, 'GENERAL'),
  ('C2', false, 15, 40, 'GENERAL');
