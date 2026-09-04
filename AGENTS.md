# Regras do Projeto MapScout

## Git e Sincronização Obrigatória
- **SEMPRE execute `git pull` antes de qualquer alteração ou análise**: múltiplos desenvolvedores atuam simultaneamente no repositório. Nunca comece uma tarefa ou análise de código sem antes garantir que a branch local está sincronizada com `origin/main`.
- **Nunca commite código com `make check` vermelho**: rode `ruff`, `mypy` e `pytest` antes de commitar ou subir alterações.
