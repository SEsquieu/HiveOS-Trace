# Quickstart

## 1) Install

```powershell
pipx install hiveos-trace
```

## 2) Run and trace any command

```powershell
hive trace run --no-open -- python -c "print('quickstart')"
```

## 3) Inspect recent runs

```powershell
hive trace ls --limit 5
```

## 4) Explain a run

```powershell
hive trace insight explain <run_id>
```

## 5) Compare two runs

```powershell
hive trace insight drift <run_id_a> <run_id_b>
```

## 6) View windowed health

```powershell
hive trace insight health --window 24h
```

