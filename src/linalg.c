/*
 * Matha 线性代数引擎 — RISC-V 裸机 C 代码
 * 目标: SiFive FE310 / RISCV32
 * 优化: -Os (代码大小优化)
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* ========== 矩阵结构 ========== */
typedef struct {{
    float data[16][16];  /* 最大 16x16 */
    int rows;
    int cols;
}} Matrix;

/* ========== 矩阵操作 ========== */

void mat_init(Matrix *m, int rows, int cols) {{
    m->rows = rows;
    m->cols = cols;
    memset(m->data, 0, sizeof(m->data));
}}

void mat_identity(Matrix *m, int n) {{
    mat_init(m, n, n);
    for (int i = 0; i < n; i++) {{
        m->data[i][i] = 1.0f;
    }}
}}

void mat_copy(Matrix *dst, const Matrix *src) {{
    memcpy(dst->data, src->data, sizeof(src->data));
    dst->rows = src->rows;
    dst->cols = src->cols;
}}

void mat_add(const Matrix *a, const Matrix *b, Matrix *result) {{
    for (int i = 0; i < a->rows; i++) {{
        for (int j = 0; j < a->cols; j++) {{
            result->data[i][j] = a->data[i][j] + b->data[i][j];
        }}
    }}
    result->rows = a->rows;
    result->cols = a->cols;
}}

void mat_mul(const Matrix *a, const Matrix *b, Matrix *result) {{
    memset(result->data, 0, sizeof(result->data));
    for (int i = 0; i < a->rows; i++) {{
        for (int k = 0; k < a->cols; k++) {{
            float aik = a->data[i][k];
            for (int j = 0; j < b->cols; j++) {{
                result->data[i][j] += aik * b->data[k][j];
            }}
        }}
    }}
    result->rows = a->rows;
    result->cols = b->cols;
}}

float mat_det(const Matrix *m) {{
    int n = m->rows;
    if (n == 1) return m->data[0][0];
    if (n == 2) return m->data[0][0] * m->data[1][1] - m->data[0][1] * m->data[1][0];

    float det = 0.0f;
    for (int j = 0; j < n; j++) {{
        /* 构建子矩阵 */
        Matrix sub;
        int si = 0;
        for (int i = 1; i < n; i++) {{
            int sj = 0;
            for (int k = 0; k < n; k++) {{
                if (k != j) sub.data[si][sj++] = m->data[i][k];
            }}
            si++;
        }}
        int sign = (j % 2 == 0) ? 1 : -1;
        det += sign * m->data[0][j] * mat_det(&sub);
    }}
    return det;
}}

/* 高斯消元法求逆 */
int mat_inv(const Matrix *m, Matrix *result) {{
    int n = m->rows;
    if (n != m->cols) return -1;

    float aug[16][32];  /* 增广矩阵 [A|I] */

    /* 构建增广矩阵 */
    for (int i = 0; i < n; i++) {{
        for (int j = 0; j < n; j++) aug[i][j] = m->data[i][j];
        for (int j = 0; j < n; j++) aug[i][n + j] = (i == j) ? 1.0f : 0.0f;
    }}

    /* 高斯-若尔当消元 */
    for (int col = 0; col < n; col++) {{
        /* 选主元 */
        int max_row = col;
        for (int row = col + 1; row < n; row++) {{
            if (fabsf(aug[row][col]) > fabsf(aug[max_row][col])) max_row = row;
        }}
        if (fabsf(aug[max_row][col]) < 1e-12f) return -1;  /* 奇异矩阵 */

        /* 交换行 */
        for (int j = 0; j < 2 * n; j++) {{
            float tmp = aug[col][j];
            aug[col][j] = aug[max_row][j];
            aug[max_row][j] = tmp;
        }}

        /* 归一化 */
        float pivot = aug[col][col];
        for (int j = 0; j < 2 * n; j++) aug[col][j] /= pivot;

        /* 消去其他行 */
        for (int row = 0; row < n; row++) {{
            if (row == col) continue;
            float factor = aug[row][col];
            for (int j = 0; j < 2 * n; j++) {{
                aug[row][j] -= factor * aug[col][j];
            }}
        }}
    }}

    /* 提取逆矩阵 */
    for (int i = 0; i < n; i++) {{
        for (int j = 0; j < n; j++) {{
            result->data[i][j] = aug[i][n + j];
        }}
    }}
    result->rows = n;
    result->cols = n;
    return 0;
}}

/* ========== 应用示例 ========== */

void example_matrix_operations(void) {{
    Matrix A, B, C, I;

    /* 初始化矩阵 A = [[1,2],[3,4]] */
    mat_init(&A, 2, 2);
    A.data[0][0] = 1.0f; A.data[0][1] = 2.0f;
    A.data[1][0] = 3.0f; A.data[1][1] = 4.0f;

    /* 初始化矩阵 B = [[5,6],[7,8]] */
    mat_init(&B, 2, 2);
    B.data[0][0] = 5.0f; B.data[0][1] = 6.0f;
    B.data[1][0] = 7.0f; B.data[1][1] = 8.0f;

    /* C = A + B */
    mat_add(&A, &B, &C);
    printf("A+B = [[%.1f,%.1f],[%.1f,%.1f]]\n",
           C.data[0][0], C.data[0][1], C.data[1][0], C.data[1][1]);

    /* C = A * B */
    mat_mul(&A, &B, &C);
    printf("A*B = [[%.1f,%.1f],[%.1f,%.1f]]\n",
           C.data[0][0], C.data[0][1], C.data[1][0], C.data[1][1]);

    /* det(A) */
    printf("det(A) = %.1f\n", mat_det(&A));

    /* A^(-1) */
    if (mat_inv(&A, &I) == 0) {{
        printf("A^(-1) = [[%.2f,%.2f],[%.2f,%.2f]]\n",
               I.data[0][0], I.data[0][1], I.data[1][0], I.data[1][1]);
    }}

    /* I = A * A^(-1) */
    mat_mul(&A, &I, &C);
    printf("A*A^(-1) = [[%.2f,%.2f],[%.2f,%.2f]]\n",
           C.data[0][0], C.data[0][1], C.data[1][0], C.data[1][1]);
}}

int main(void) {{
    example_matrix_operations();
    return 0;
}}
