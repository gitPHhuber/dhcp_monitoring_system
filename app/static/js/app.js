// app/static/js/app.js

$(document).ready(function() {

    // Функция обновления таблицы (AJAX)
    function updateTable() {
        $.ajax({
            url: $("#leases-table").data("url"), //  <--  Берем URL из data-url таблицы
            type: "GET",
            data: {
                status: $("#leases-table").data("status"),
                q: $("#leases-table").data("search-query")  //  <--  Берем search-query
            },
            success: function(data) {
                $("#leases-table").html(data); //  <--  Заменяем содержимое таблицы
            },
            error: function(xhr, status, error) {
                console.error("Error updating table:", error);
                alert("Error updating table: " + error);
            }
        });
    }

    // Делегирование событий (ОДИН ОБРАБОТЧИК ДЛЯ ВСЕХ КНОПОК)
    $("#leases-table").on("click", ".take-btn, .release-btn, .complete-btn, .pending-btn, .broken-btn, .reset-btn, .delete-btn, .complete-with-comment-btn", function(event) {
        event.preventDefault();
        let url = $(this).data("url");

        if (!url) {
            console.error("No URL found for action button");
            return;
        }

        let method = $(this).hasClass("delete-btn") ? "DELETE" : "POST";

        //  Добавляем проверку для complete-with-comment-btn
        if ($(this).hasClass("complete-with-comment-btn")) {
            //  Для этой кнопки модальное окно открывается через Bootstrap,
            //  поэтому AJAX-запрос здесь не нужен.  Он будет в обработчике
            //  кнопки "Submit" модального окна.
            return;
        }

        $.ajax({
            url: url,
            type: method,
            success: function(response) {
                console.log(response.message);
                updateTable(); // Обновляем таблицу
            },
            error: function(xhr, status, error) {
                console.error("Error performing action:", error);
                alert(xhr.responseJSON ? xhr.responseJSON.message : "An error occurred.");
            }
        });
    });

    // Обработчик для кнопки "Submit" в модальном окне "Complete with Comment"
    $(document).on("click", ".complete-comment-submit-btn", function(event) { // Используем document, т.к. модальное окно динамическое
        let leaseId = $(this).data("lease-id");
        let comment = $("#comment" + leaseId).val();
        let url = $(`#completeCommentModal${leaseId} .complete-with-comment-btn`).data('url'); //Берем из кнопки

        $.ajax({
            url: url,
            type: "POST",
            contentType: "application/json", // Важно для отправки JSON
            data: JSON.stringify({ comment: comment }), // Отправляем комментарий
            success: function(response) {
                console.log(response.message);
                updateTable(); // Обновляем таблицу
                $(`#completeCommentModal${leaseId}`).modal('hide'); // Закрываем модальное окно
                 $("#comment" + leaseId).val(''); //Очищаем поле
            },
            error: function(xhr, status, error) {
                console.error("Error completing with comment:", error);
                alert(xhr.responseJSON ? xhr.responseJSON.message : "An error occurred.");
            }
        });
    });

    // Переключение темной темы
    $("#dark-mode-toggle").click(function() {
        let currentTheme = $("body").hasClass("dark-mode") ? "dark" : "light";
        let newTheme = currentTheme === "light" ? "dark" : "light"; //  <--  Определяем НОВУЮ тему

        $.ajax({
            url: "{{ url_for('main.toggle_dark_mode') }}?theme=" + currentTheme, //  <--  Передаём ТЕКУЩУЮ тему
            type: "GET",
            success: function(data) {
                if (data.theme === 'dark') {
                    $("body").addClass("dark-mode");
                    localStorage.setItem("theme", "dark");  //  <--  Сохраняем в localStorage
                } else {
                    $("body").removeClass("dark-mode");
                    localStorage.setItem("theme", "light"); //  <--  Сохраняем в localStorage
                }
            }
        });
    });

    //  Проверяем, есть ли сохранённая тема в localStorage, при загрузке страницы
    let savedTheme = localStorage.getItem("theme");
    if (savedTheme === "dark") {
        $("body").addClass("dark-mode");
    } else if (savedTheme === "light") {
        $("body").removeClass("dark-mode");
    }


    // Периодическое обновление (раскомментируем, когда всё остальное заработает)
    // setInterval(updateTable, 30000);

    // Начальное обновление
    updateTable();
});