# Authorization Service

Вспомогательный сервис-сабмодуль, в котором собранны все базовые потребности сервисов авторизации, с разделением прав доступа (групп). Этот сабмодуль будет использоваться в проекте телеграм бота с коллекционированием лего минифигурок. Возможно дальнейшее использование

# Полное API данного 
## Права доступа:
Метод   | Путь                                           | Описание                                  | Тело запроса              | Ответ
--------|------------------------------------------------|-------------------------------------------|---------------------------|-------------------------------
GET     | /permissions/rules/                            | Получить список всех правил               | —                         | List[PermissionRead]
POST    | /permissions/rules/                            | Создать новое правило                     | PermissionCreate          | PermissionRead
PATCH   | /permissions/rules/{perm_id}                   | Переименовать правило                     | PermissionRename          | PermissionRead
DELETE  | /permissions/rules/{perm_id}                   | Удалить правило                           | —                         | 204 No Content
GET     | /permissions/groups/                           | Получить список всех групп                | —                         | List[PermissionGroupRead]
POST    | /permissions/groups/                           | Создать новую группу                      | PermissionGroupCreate     | PermissionGroupRead
GET     | /permissions/groups/{group_id}                 | Подробности группы с её правилами         | —                         | PermissionGroupRead
POST    | /permissions/groups/{group_id}/rules/{perm_id} | Добавить правило в группу                 | —                         | PermissionGroupRead
DELETE  | /permissions/groups/{group_id}/rules/{perm_id} | Удалить правило из группы                 | —                         | PermissionGroupRead


## Работа с пользователем:
Метод   | Путь                                           | Описание                                  | Тело запроса   | Ответ
--------|------------------------------------------------|-------------------------------------------|----------------|-----------------
GET     | /users/                                        | Получить список всех пользователей         | —              | List[UserRead]
POST    | /users/                                        | Создать пользователя                       | UserCreate     | UserRead
GET     | /users/{user_id}                               | Получить одного пользователя               | —              | UserRead
PATCH   | /users/{user_id}                               | Обновить данные пользователя               | UserUpdate     | UserRead
DELETE  | /users/{user_id}                               | Удалить пользователя                       | —              | 204 No Content
POST    | /users/{user_id}/groups/{group_id}             | Добавить группу прав пользователю          | —              | UserRead
DELETE  | /users/{user_id}/groups/{group_id}             | Удалить группу прав у пользователя         | —              | UserRead
