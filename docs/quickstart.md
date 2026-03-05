# Quickstart

## 1) Install

```
pipx install hiveos-trace
```

## 2) Run and trace any command

```
hive trace run --no-open -- python -c "print('quickstart')"
```

## 3) Inspect recent runs

```
hive trace ls --limit 5
```

## 4) Explain a run

```
hive trace insight explain <run_id>
```

## 5) Compare two runs

```
hive trace insight drift <run_id_a> <run_id_b>
```

## 6) View windowed health

```
hive trace insight health --window 24h
```

